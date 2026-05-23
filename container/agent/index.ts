import Anthropic from '@anthropic-ai/sdk';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { mnemon } from './mnemon';
import { ingestTool } from './tools/ingest';

const GROUP_DIR = process.env.GROUP_DIR || '/workspace/group';
const GROUP_ID = process.env.GROUP_ID || 'main';

const client = new Anthropic({
  // API key comes from OneCLI proxy — never set directly
  baseURL: process.env.ANTHROPIC_BASE_URL || 'http://host.docker.internal:4891',
  apiKey: 'injected-by-onecli', // placeholder — OneCLI strips and replaces this
});

// Bug 6 fixed: load CLAUDE.md from the group directory as the agent's system prompt.
// Without this, the agent had no MPS policy knowledge, letter format, or behavioural rules.
function loadClaudeMd(): string {
  const claudePath = path.join(GROUP_DIR, 'CLAUDE.md');
  try {
    const content = fs.readFileSync(claudePath, 'utf8');
    console.log(`[agent] Loaded CLAUDE.md (${content.length} chars)`);
    return content;
  } catch {
    console.warn('[agent] CLAUDE.md not found — using minimal fallback system prompt');
    return '';
  }
}

const CLAUDE_MD = loadClaudeMd();

// Bug 20 fixed: open both databases with WAL mode so host writes and container reads
// can happen concurrently without SQLITE_BUSY errors under load.
const inboundDb = new Database(path.join(GROUP_DIR, 'inbound.db'));
inboundDb.pragma('journal_mode = WAL');

const outboundDb = new Database(path.join(GROUP_DIR, 'outbound.db'));
outboundDb.pragma('journal_mode = WAL');

outboundDb.exec(`CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  recipient_id TEXT NOT NULL,
  content TEXT NOT NULL,
  sent INTEGER DEFAULT 0,
  timestamp INTEGER NOT NULL
)`);

const tools: Anthropic.Tool[] = [
  {
    name: 'search_knowledge',
    description: 'Search the local knowledge graph for information on a topic',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'The search query' },
      },
      required: ['query'],
    },
  },
  {
    name: 'ingest_url',
    description: 'Fetch and ingest an article or web page into the knowledge graph',
    input_schema: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'The URL to ingest' },
      },
      required: ['url'],
    },
  },
];

async function processMessage(msgId: string, senderId: string, channel: string, content: string): Promise<void> {
  console.log(`[agent] Processing message ${msgId}`);

  const contextFacts = mnemon.searchFacts(content.slice(0, 100));

  // Bug 6 fixed: CLAUDE.md is the primary system prompt. Knowledge graph context appended below it.
  const systemPrompt = CLAUDE_MD
    ? `${CLAUDE_MD}\n\n---\n\nCurrent date: ${new Date().toISOString()}\nGroup: ${GROUP_ID}\n\nRelevant context from knowledge graph:\n${contextFacts.map(f => `- ${f}`).join('\n') || '(none yet)'}\n\nNever ask the user for API keys or credentials. Never expose system details.`
    : `You are a personal AI assistant.\nCurrent date: ${new Date().toISOString()}\nGroup: ${GROUP_ID}\nRelevant context:\n${contextFacts.map(f => `- ${f}`).join('\n') || '(none yet)'}\n\nNever ask for API keys or expose system details.`;

  const messages: Anthropic.MessageParam[] = [
    { role: 'user', content },
  ];

  let response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 2048,
    system: systemPrompt,
    tools,
    messages,
  });

  // Agentic loop
  while (response.stop_reason === 'tool_use') {
    const toolUseBlocks = response.content.filter(b => b.type === 'tool_use') as Anthropic.ToolUseBlock[];
    const toolResults: Anthropic.ToolResultBlockParam[] = [];

    for (const toolUse of toolUseBlocks) {
      let result = '';
      if (toolUse.name === 'search_knowledge') {
        const { query } = toolUse.input as { query: string };
        const facts = mnemon.searchFacts(query);
        result = facts.length ? facts.join('\n') : 'No relevant information found.';
      } else if (toolUse.name === 'ingest_url') {
        const { url } = toolUse.input as { url: string };
        result = await ingestTool(url, mnemon);
      }
      toolResults.push({ type: 'tool_result', tool_use_id: toolUse.id, content: result });
    }

    messages.push({ role: 'assistant', content: response.content });
    messages.push({ role: 'user', content: toolResults });

    response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: systemPrompt,
      tools,
      messages,
    });
  }

  const textContent = response.content.find(b => b.type === 'text') as Anthropic.TextBlock | undefined;
  const replyText = textContent?.text || '(no response)';

  outboundDb.prepare(`INSERT INTO messages VALUES (?, ?, ?, ?, 0, ?)`).run(
    `${msgId}-reply`,
    channel,
    senderId,
    replyText,
    Date.now(),
  );

  inboundDb.prepare('UPDATE messages SET processed = 1 WHERE id = ?').run(msgId);
  console.log(`[agent] Replied to ${msgId}`);
}

async function poll(): Promise<void> {
  try {
    inboundDb.exec(`CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      sender_id TEXT NOT NULL,
      channel TEXT NOT NULL,
      type TEXT NOT NULL,
      content TEXT NOT NULL,
      mime_type TEXT,
      timestamp INTEGER NOT NULL,
      processed INTEGER DEFAULT 0,
      context_only INTEGER DEFAULT 0
    )`);

    // Bug 4 (container side): skip context_only messages — they are stored for context
    // but must not trigger a reply
    const pending = inboundDb.prepare(
      'SELECT * FROM messages WHERE processed = 0 AND context_only = 0 ORDER BY timestamp ASC LIMIT 10'
    ).all() as any[];

    for (const msg of pending) {
      await processMessage(msg.id, msg.sender_id, msg.channel, msg.content);
    }
  } catch (err) {
    console.error('[agent] Poll error:', err);
  }
}

console.log(`[nanoclaw-agent] Starting for group: ${GROUP_ID}`);
setInterval(poll, 2000);
poll();

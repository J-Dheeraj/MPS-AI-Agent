import readline from 'readline';
import { v4 as uuidv4 } from 'uuid';
import { InboundMessage } from '../router';
import { logger } from '../logger';

export function startCLI(router: (msg: InboundMessage) => Promise<void>): void {
  if (!process.stdin.isTTY) return;

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  rl.setPrompt('nanoclaw> ');
  rl.prompt();

  rl.on('line', async (line) => {
    const content = line.trim();
    if (!content) { rl.prompt(); return; }

    const msg: InboundMessage = {
      id: uuidv4(),
      groupId: 'main',
      senderId: 'cli-user',
      channel: 'cli',
      type: 'text',
      content,
      timestamp: Date.now(),
    };

    try {
      await router(msg);
    } catch (err) {
      logger.error(err);
    }
    rl.prompt();
  });
}

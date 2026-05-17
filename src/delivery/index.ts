import fs from 'fs';
import path from 'path';
import Database from 'better-sqlite3';
import { logger } from '../logger';

const GROUPS_DIR = path.join(process.env.HOME || '/root', 'nanoclaw', 'groups');

interface OutboundMessage {
  id: string;
  channel: string;
  recipient_id: string;
  content: string;
  sent: number;
  timestamp: number;
}

export function startDelivery(): void {
  setInterval(() => pollAllGroups(), 1000);
}

function pollAllGroups(): void {
  if (!fs.existsSync(GROUPS_DIR)) return;
  const groups = fs.readdirSync(GROUPS_DIR);
  for (const group of groups) {
    const outboundPath = path.join(GROUPS_DIR, group, 'outbound.db');
    if (!fs.existsSync(outboundPath)) continue;
    try {
      deliverPending(group, outboundPath);
    } catch (err) {
      logger.error({ err, group }, 'Delivery error');
    }
  }
}

function deliverPending(groupId: string, dbPath: string): void {
  const db = new Database(dbPath);
  db.exec(`CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    content TEXT NOT NULL,
    sent INTEGER DEFAULT 0,
    timestamp INTEGER NOT NULL
  )`);

  const pending = db.prepare('SELECT * FROM messages WHERE sent = 0').all() as OutboundMessage[];
  for (const msg of pending) {
    try {
      // In production: dispatch to the appropriate channel sender
      logger.info({ groupId, channel: msg.channel, recipient: msg.recipient_id }, `Delivering: ${msg.content.slice(0, 80)}`);
      db.prepare('UPDATE messages SET sent = 1 WHERE id = ?').run(msg.id);
    } catch (err) {
      logger.error({ err, msgId: msg.id }, 'Failed to deliver message');
    }
  }
  db.close();
}

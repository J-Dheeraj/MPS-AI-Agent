import fs from 'fs';
import path from 'path';
import { logger } from '../logger';

interface GroupAllowlist {
  mode: 'drop' | 'trigger';
  allowedSenders: string[];
}

interface AllowlistConfig {
  defaultMode: 'drop' | 'trigger';
  groups: Record<string, GroupAllowlist>;
}

function loadConfig(): AllowlistConfig | null {
  const configPath = path.join(process.env.HOME || '/root', '.config', 'nanoclaw', 'sender-allowlist.json');
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch {
    logger.warn('sender-allowlist.json not found — all senders allowed (configure before going live)');
    return null;
  }
}

export function checkSenderAllowed(groupId: string, senderId: string): boolean {
  const config = loadConfig();
  if (!config) return true; // permissive until configured

  const groupConfig = config.groups[groupId];
  const mode = groupConfig?.mode ?? config.defaultMode;
  const allowedSenders = groupConfig?.allowedSenders ?? [];

  if (allowedSenders.includes(senderId)) return true;
  if (mode === 'drop') return false;
  return false; // trigger mode: still block non-listed senders from triggering
}

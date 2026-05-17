import fs from 'fs';
import path from 'path';
import { logger } from '../logger';

interface MountAllowlist {
  allowedPaths: string[];
  blockedPatterns: string[];
}

function loadConfig(): MountAllowlist | null {
  const configPath = path.join(process.env.HOME || '/root', '.config', 'nanoclaw', 'mount-allowlist.json');
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch {
    logger.warn('mount-allowlist.json not found');
    return null;
  }
}

export function validateMountPath(mountPath: string): boolean {
  const config = loadConfig();
  if (!config) return false; // deny by default if no config

  // Resolve ~ in allowedPaths
  const home = process.env.HOME || '/root';
  const allowedResolved = config.allowedPaths.map(p => p.replace('~', home));

  const isAllowed = allowedResolved.some(allowed => mountPath.startsWith(allowed));
  if (!isAllowed) return false;

  const isBlocked = config.blockedPatterns.some(pattern => {
    if (pattern.startsWith('*.')) {
      return mountPath.endsWith(pattern.slice(1));
    }
    return mountPath.includes(pattern);
  });

  return !isBlocked;
}

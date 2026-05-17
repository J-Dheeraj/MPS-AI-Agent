import { execSync } from 'child_process';
import path from 'path';
import { logger } from '../logger';
import { validateMountPath } from '../security/mountAllowlist';

const GROUPS_DIR = path.join(process.env.HOME || '/root', 'nanoclaw', 'groups');
const ONECLI_PORT = parseInt(process.env.ONECLI_PORT || '4891');

export class ContainerRunner {
  private running = new Map<string, string>(); // groupId -> containerId

  async ensureRunning(groupId: string): Promise<void> {
    if (this.running.has(groupId)) {
      // Check if still alive
      try {
        const out = execSync(`docker inspect -f '{{.State.Running}}' ${this.running.get(groupId)}`).toString().trim();
        if (out === 'true') return;
      } catch {
        this.running.delete(groupId);
      }
    }

    const groupDir = path.join(GROUPS_DIR, groupId);

    // Validate mount path against allowlist
    if (!validateMountPath(groupDir)) {
      throw new Error(`Mount denied for group directory: ${groupDir}`);
    }

    const containerName = `nanoclaw-agent-${groupId}`;

    // Remove stopped container if exists
    try { execSync(`docker rm -f ${containerName} 2>/dev/null`); } catch {}

    const args = [
      'run', '-d',
      '--name', containerName,
      '--network', 'host',  // shares host network so OneCLI proxy is reachable
      '--env', `ONECLI_PROXY=http://127.0.0.1:${ONECLI_PORT}`,
      '--env', `GROUP_ID=${groupId}`,
      '--env', `GROUP_DIR=/workspace/group`,
      '--env', `ANTHROPIC_BASE_URL=http://127.0.0.1:${ONECLI_PORT}`,
      '-v', `${groupDir}:/workspace/group`,
      'nanoclaw-agent:latest',
    ];

    logger.info({ groupId, containerName }, 'Spawning agent container');
    const result = execSync(`docker ${args.join(' ')}`).toString().trim();
    this.running.set(groupId, result);
    logger.info({ groupId, containerId: result }, 'Container started');
  }
}

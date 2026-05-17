import cron from 'node-cron';
import { logger } from '../logger';

interface ScheduledTask {
  id: string;
  cronExpr: string;
  groupId: string;
  prompt: string;
}

const tasks = new Map<string, cron.ScheduledTask>();

export function startScheduler(): void {
  logger.info('Task scheduler started');
}

export function registerTask(task: ScheduledTask): void {
  const job = cron.schedule(task.cronExpr, () => {
    logger.info({ taskId: task.id }, 'Scheduled task triggered');
    // Inject scheduled prompt into group's inbound.db
  });
  tasks.set(task.id, job);
  logger.info({ task }, 'Task registered');
}

export function listTasks(): ScheduledTask[] {
  return []; // TODO: persist to SQLite
}

import express from 'express';
import cors from 'cors';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { InboundMessage } from '../router';
import { logger } from '../logger';

const WEB_HOST = process.env.WEB_HOST || '127.0.0.1';
const WEB_PORT = parseInt(process.env.WEB_PORT || '3080');

export function startWebUI(router: (msg: InboundMessage) => Promise<void>): void {
  const app = express();
  app.use(cors({ origin: false })); // no CORS — localhost only
  app.use(express.json({ limit: '10mb' }));
  app.use(express.static(path.join(__dirname, '../../public')));

  app.post('/api/message', async (req, res) => {
    const { content, type = 'text', groupId = 'main' } = req.body;
    if (!content) return res.status(400).json({ error: 'content required' });

    const msg: InboundMessage = {
      id: uuidv4(),
      groupId,
      senderId: 'webui-user',
      channel: 'webui',
      type,
      content,
      timestamp: Date.now(),
    };

    try {
      await router(msg);
      res.json({ ok: true, id: msg.id });
    } catch (err) {
      logger.error(err);
      res.status(500).json({ error: 'routing failed' });
    }
  });

  app.listen(WEB_PORT, WEB_HOST, () => {
    logger.info(`Web UI listening on http://${WEB_HOST}:${WEB_PORT}`);
  });
}

import { Router, Request, Response, NextFunction } from 'express';
import { conversationEngine } from '../services/conversation-engine.js';
import { StartConversationRequestSchema, SendMessageRequestSchema } from '../types.js';

const router = Router();

/**
 * POST /api/conversation/start
 * Start a new triage conversation
 */
router.post('/start', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const input = StartConversationRequestSchema.parse(req.body);
    const result = await conversationEngine.startConversation(input.patientId);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/conversation/message
 * Send a message in an existing conversation
 */
router.post('/message', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const input = SendMessageRequestSchema.parse(req.body);
    const result = await conversationEngine.processMessage(
      input.conversationId,
      input.message
    );
    res.json(result);
  } catch (error) {
    next(error);
  }
});

/**
 * GET /api/conversation/:id
 * Get conversation state
 */
router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const conversation = await conversationEngine.getConversation(req.params.id);
    if (!conversation) {
      res.status(404).json({ error: 'Conversation not found' });
      return;
    }
    res.json(conversation);
  } catch (error) {
    next(error);
  }
});

export { router as conversationRouter };

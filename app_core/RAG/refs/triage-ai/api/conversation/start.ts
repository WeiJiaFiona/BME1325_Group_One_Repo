import type { VercelRequest, VercelResponse } from '@vercel/node';
import { randomUUID } from 'crypto';
import { checkRateLimit } from '../lib/rate-limiter';

// In-memory store for serverless (will reset between cold starts - fine for demo)
const conversations = new Map<string, any>();

const GREETING_MESSAGE = "Hi, I'm TriageAI, your virtual health assistant. I'm here to help understand your symptoms and guide you to the right care. What's bringing you in today?";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Rate limit: 10 conversation starts per minute per IP
  const allowed = await checkRateLimit(req, res, 'start');
  if (!allowed) return;

  const conversationId = randomUUID();

  conversations.set(conversationId, {
    id: conversationId,
    messages: [{ role: 'assistant', content: GREETING_MESSAGE }],
    collectedData: { symptoms: [] },
    stage: 'collecting',
    createdAt: new Date().toISOString(),
  });

  return res.json({
    conversationId,
    message: GREETING_MESSAGE,
    stage: 'collecting',
    isComplete: false,
  });
}

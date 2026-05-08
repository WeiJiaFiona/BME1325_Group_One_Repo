import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { conversationRouter } from './routes/conversation.js';
import { errorHandler } from './middleware/error-handler.js';

const app = express();
const PORT = process.env.PORT || 3001;

// Security middleware
app.use(helmet());

// CORS - allow frontend origins
app.use(cors({
  origin: process.env.CORS_ORIGIN || ['http://localhost:5173', 'http://localhost:3000'],
  credentials: true,
}));

// Body parsing
app.use(express.json({ limit: '10kb' }));

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    version: '0.1.0',
  });
});

// Conversation routes
app.use('/api/conversation', conversationRouter);

// Error handling
app.use(errorHandler);

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: 'NOT_FOUND',
    message: `Route ${req.method} ${req.path} not found`,
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`
╔═══════════════════════════════════════════════════════════╗
║                    TriageAI API Server                     ║
╠═══════════════════════════════════════════════════════════╣
║  Status:  Running                                          ║
║  Port:    ${PORT}                                             ║
║  Health:  http://localhost:${PORT}/api/health                 ║
╚═══════════════════════════════════════════════════════════╝
  `);
});

export default app;

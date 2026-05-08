import { Request, Response, NextFunction } from 'express';
import { ZodError } from 'zod';

export function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
): void {
  console.error('Error:', err);

  // Zod validation errors
  if (err instanceof ZodError) {
    res.status(400).json({
      error: 'VALIDATION_ERROR',
      message: 'Invalid input',
      details: err.errors.map(e => ({
        path: e.path.join('.'),
        message: e.message,
      })),
    });
    return;
  }

  // LLM API errors
  if (err.message?.includes('GROQ') || err.message?.includes('API')) {
    res.status(503).json({
      error: 'AI_SERVICE_ERROR',
      message: 'AI service is temporarily unavailable. Please try again.',
    });
    return;
  }

  // Conversation not found
  if (err.message?.includes('not found')) {
    res.status(404).json({
      error: 'NOT_FOUND',
      message: err.message,
    });
    return;
  }

  // Default server error
  res.status(500).json({
    error: 'INTERNAL_ERROR',
    message: process.env.NODE_ENV === 'production'
      ? 'An unexpected error occurred'
      : err.message,
  });
}

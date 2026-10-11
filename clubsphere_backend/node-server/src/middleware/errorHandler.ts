import { Request, Response, NextFunction } from 'express';
import { ZodError } from 'zod';

export function errorHandler(err: any, req: Request, res: Response, next: NextFunction): void {
  console.error(`[ERROR] ${req.method} ${req.originalUrl}:`, err);

  if (err instanceof ZodError) {
    res.status(400).json({
      error: 'Validation failed',
      details: err.errors.map((e) => ({
        path: e.path.join('.'),
        message: e.message,
      })),
    });
    return;
  }

  const statusCode = typeof err.statusCode === 'number' ? err.statusCode : 500;
  const message = err.message || 'An unexpected internal error occurred';

  res.status(statusCode).json({
    error: message,
    code: err.code || 'INTERNAL_ERROR',
  });
}

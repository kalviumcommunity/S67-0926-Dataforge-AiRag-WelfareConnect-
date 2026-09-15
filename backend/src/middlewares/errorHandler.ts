import { Request, Response, NextFunction } from 'express';

export function errorHandler(err: Error, req: Request, res: Response, next: NextFunction): void {
  console.error(`[Error] ${req.method} ${req.path}:`, err);

  res.status(500).json({
    status: 'ERROR',
    message: err.message || 'An unexpected error occurred',
  });
}

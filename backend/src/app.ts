import express, { Express } from 'express';
import cors from 'cors';
import { env } from './config/env';
import healthRoutes from './routes/healthRoutes';
import authRoutes from './routes/authRoutes';
import collectionRoutes from './routes/collectionRoutes';
import documentRoutes from './routes/documentRoutes';
import queryRoutes from './routes/queryRoutes';
import feedbackRoutes from './routes/feedbackRoutes';
import auditRoutes from './routes/auditRoutes';
import { errorHandler } from './middlewares/errorHandler';
import { requestLogger } from './middlewares/requestLogger';

export function createApp(): Express {
  const app = express();

  // Core Middlewares
  app.use(cors({ origin: '*' }));
  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));
  app.use(requestLogger);

  // Health-check endpoints (both root and versioned)
  app.use('/health', healthRoutes);
  app.use('/api/health', healthRoutes);
  app.use(`${env.API_PREFIX}/health`, healthRoutes);

  // Domain & Authentication API Routes
  app.use(`${env.API_PREFIX}/auth`, authRoutes);
  app.use(`${env.API_PREFIX}/collections`, collectionRoutes);
  app.use(`${env.API_PREFIX}/documents`, documentRoutes);
  app.use(`${env.API_PREFIX}/query`, queryRoutes);
  app.use(`${env.API_PREFIX}/feedback`, feedbackRoutes);
  app.use(`${env.API_PREFIX}/audit`, auditRoutes);

  // Fallback 404 handler
  app.use((req, res) => {
    res.status(404).json({
      status: 'ERROR',
      message: `Route not found: ${req.method} ${req.path}`,
    });
  });

  // Global Error Handler
  app.use(errorHandler);

  return app;
}

export const app = createApp();

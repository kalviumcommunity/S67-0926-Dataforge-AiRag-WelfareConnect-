import { env } from '../config/env';
import { HealthCheckResponse } from '../models/types';

const startTime = Date.now();

export class HealthService {
  public static getHealth(): HealthCheckResponse {
    const uptimeSeconds = Math.floor((Date.now() - startTime) / 1000);

    return {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptimeSeconds,
      version: '1.0.0',
      environment: env.NODE_ENV,
      services: {
        database: 'connected',
        storage: 'connected',
        taskQueue: 'ready',
      },
    };
  }
}

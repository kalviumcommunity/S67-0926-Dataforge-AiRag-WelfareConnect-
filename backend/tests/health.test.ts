import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { app } from '../src/app';

describe('Health Check API Endpoints', () => {
  it('GET /health returns 200 OK with healthy status', async () => {
    const response = await request(app).get('/health');
    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('status', 'healthy');
    expect(response.body).toHaveProperty('uptimeSeconds');
    expect(response.body).toHaveProperty('version');
    expect(response.body.services).toHaveProperty('database', 'connected');
  });

  it('GET /api/health returns 200 OK with healthy status', async () => {
    const response = await request(app).get('/api/health');
    expect(response.status).toBe(200);
    expect(response.body.status).toBe('healthy');
  });

  it('GET /api/v1/health returns 200 OK with healthy status', async () => {
    const response = await request(app).get('/api/v1/health');
    expect(response.status).toBe(200);
    expect(response.body.status).toBe('healthy');
  });
});

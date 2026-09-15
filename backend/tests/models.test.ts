import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { app } from '../src/app';

describe('API Routes & Model Integration', () => {
  it('GET /api/v1/collections returns collections array', async () => {
    const response = await request(app).get('/api/v1/collections');
    expect(response.status).toBe(200);
    expect(response.body.status).toBe('SUCCESS');
    expect(Array.isArray(response.body.data)).toBe(true);
    expect(response.body.data.length).toBeGreaterThan(0);
    expect(response.body.data[0]).toHaveProperty('id');
    expect(response.body.data[0]).toHaveProperty('name');
  });

  it('POST /api/v1/query returns grounded answer with citations and legal disclaimer', async () => {
    const response = await request(app).post('/api/v1/query').send({
      queryText: 'What is the land limit for PM-Kisan farmer subsidy?',
    });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('SUCCESS');
    expect(response.body.isGrounded).toBe(true);
    expect(response.body).toHaveProperty('disclaimer');
    expect(response.body.answer.citations.length).toBeGreaterThan(0);
    expect(response.body.answer.citations[0]).toHaveProperty('pageNumber');
    expect(response.body.answer.citations[0]).toHaveProperty('documentTitle');
  });

  it('POST /api/v1/query returns refusal fallback when question is outside uploaded documents', async () => {
    const response = await request(app).post('/api/v1/query').send({
      queryText: 'How to apply for visa to Mars?',
    });

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('NOT_FOUND');
    expect(response.body.isGrounded).toBe(false);
    expect(response.body.fallbackMessage).toContain(
      'not available in the uploaded official scheme documents'
    );
    expect(response.body).toHaveProperty('disclaimer');
  });
});

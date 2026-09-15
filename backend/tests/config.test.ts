import { describe, it, expect } from 'vitest';
import { env } from '../src/config/env';

describe('Environment Configuration', () => {
  it('loads valid default configuration parameters', () => {
    expect(env.PORT).toBeDefined();
    expect(typeof env.PORT).toBe('number');
    expect(env.API_PREFIX).toBe('/api/v1');
    expect(env.APP_NAME).toBe('WelfareSchemeDocumentAssistant');
    expect(env.SIMILARITY_THRESHOLD).toBeGreaterThan(0);
    expect(env.MAX_RETRIEVED_CHUNKS).toBeGreaterThan(0);
  });
});

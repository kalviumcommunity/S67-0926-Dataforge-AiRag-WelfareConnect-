import dotenv from 'dotenv';
import { z } from 'zod';

// Load environment variables from .env if present
dotenv.config();

const envSchema = z.object({
  PORT: z
    .string()
    .default('4000')
    .transform(val => parseInt(val, 10)),
  NODE_ENV: z.enum(['development', 'staging', 'production', 'test']).default('development'),
  APP_NAME: z.string().default('WelfareSchemeDocumentAssistant'),
  API_PREFIX: z.string().default('/api/v1'),
  CORS_ORIGIN: z.string().default('http://localhost:3000'),

  // Database
  DATABASE_URL: z
    .string()
    .default('postgresql://postgres_user:placeholder_password@localhost:5432/welfare_rag_db'),
  DB_POOL_MIN: z
    .string()
    .default('2')
    .transform(val => parseInt(val, 10)),
  DB_POOL_MAX: z
    .string()
    .default('10')
    .transform(val => parseInt(val, 10)),

  // Storage
  STORAGE_ENDPOINT: z.string().default('http://localhost:9000'),
  STORAGE_REGION: z.string().default('us-east-1'),
  STORAGE_BUCKET_NAME: z.string().default('welfare-documents-bucket'),
  STORAGE_USE_SSL: z
    .string()
    .default('false')
    .transform(val => val === 'true'),

  // Queue
  REDIS_URL: z.string().default('redis://localhost:6379/0'),

  // AI & RAG Configuration (Placeholders)
  EMBEDDING_MODEL_NAME: z.string().default('text-embedding-3-small'),
  EMBEDDING_DIMENSIONS: z
    .string()
    .default('768')
    .transform(val => parseInt(val, 10)),
  LLM_MODEL_NAME: z.string().default('gpt-4o-mini'),
  SIMILARITY_THRESHOLD: z
    .string()
    .default('0.65')
    .transform(val => parseFloat(val)),
  MAX_RETRIEVED_CHUNKS: z
    .string()
    .default('5')
    .transform(val => parseInt(val, 10)),
  STRICT_CITATION_ENFORCEMENT: z
    .string()
    .default('true')
    .transform(val => val === 'true'),
});

export type EnvConfig = z.infer<typeof envSchema>;

let config: EnvConfig;

try {
  config = envSchema.parse(process.env);
} catch (error) {
  console.warn(
    '⚠️ Some environment variables did not pass strict validation, using safe defaults:',
    error
  );
  config = envSchema.parse({});
}

export const env = config;

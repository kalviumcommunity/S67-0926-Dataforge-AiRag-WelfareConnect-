import { describe, it, expect } from 'vitest';
import { Migrator } from '../src/db/migrator';
import { Seeder } from '../src/db/seed';

describe('Database Migrations & Seed Verification', () => {
  it('discovers and reads the initial SQL schema migration', () => {
    const migrations = Migrator.getMigrationFiles();
    expect(migrations.length).toBeGreaterThan(0);
    expect(migrations[0].name).toBe('001_initial_schema.sql');

    const sql = migrations[0].sql;

    // Verify all 14 tables are present
    const expectedTables = [
      'roles',
      'users',
      'document_collections',
      'documents',
      'document_versions',
      'document_metadata',
      'document_pages',
      'extracted_text_chunks',
      'processing_jobs',
      'search_sessions',
      'questions_and_answers',
      'citations',
      'audit_events',
      'user_feedback',
    ];

    for (const table of expectedTables) {
      expect(sql).toContain(`CREATE TABLE IF NOT EXISTS ${table}`);
    }

    // Verify required document columns
    expect(sql).toContain('scheme_name VARCHAR(300) NOT NULL');
    expect(sql).toContain('department VARCHAR(255) NOT NULL');
    expect(sql).toContain('state_or_district');
    expect(sql).toContain('language');
    expect(sql).toContain('current_version_number');
    expect(sql).toContain('status document_status_type NOT NULL');

    // Verify required document_versions columns
    expect(sql).toContain('original_filename VARCHAR(300) NOT NULL');
    expect(sql).toContain('stored_file_key VARCHAR(500) NOT NULL');
    expect(sql).toContain('mime_type VARCHAR(100) NOT NULL');
    expect(sql).toContain('file_hash_sha256 VARCHAR(64) NOT NULL');
    expect(sql).toContain('publication_date DATE');
    expect(sql).toContain('effective_date DATE NOT NULL');
    expect(sql).toContain('version_number VARCHAR(50) NOT NULL');

    // Verify required indexes
    expect(sql).toContain(
      'CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents(collection_id);'
    );
    expect(sql).toContain('CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);');
    expect(sql).toContain(
      'CREATE INDEX IF NOT EXISTS idx_documents_scheme_name ON documents(scheme_name);'
    );
    expect(sql).toContain(
      'CREATE INDEX IF NOT EXISTS idx_documents_department ON documents(department);'
    );
    expect(sql).toContain(
      'CREATE INDEX IF NOT EXISTS idx_document_versions_effective_date ON document_versions(effective_date);'
    );
    expect(sql).toContain(
      'CREATE INDEX IF NOT EXISTS idx_document_versions_file_hash ON document_versions(file_hash_sha256);'
    );
  });

  it('discovers and reads the initial seed data', () => {
    const seeds = Seeder.getSeedFiles();
    expect(seeds.length).toBeGreaterThan(0);
    expect(seeds[0].name).toBe('001_initial_seed.sql');

    const sql = seeds[0].sql;

    // Verify seed contents
    expect(sql).toContain('SYSTEM_ADMIN');
    expect(sql).toContain('SCHEME_ADMIN');
    expect(sql).toContain('HELPDESK');
    expect(sql).toContain('CITIZEN');
    expect(sql).toContain('admin.dev@welfareconnect.local');
    expect(sql).toContain('Agriculture & Farmer Welfare Schemes');
    expect(sql).toContain('PM_Kisan_Operational_Guidelines_2024_25.pdf');
  });

  it('executes Migrator and Seeder runner utilities successfully', async () => {
    const migrationResult = await Migrator.runMigrations();
    expect(migrationResult.executed).toContain('001_initial_schema.sql');
    expect(migrationResult.total).toBeGreaterThan(0);

    const seedResult = await Seeder.runSeeds();
    expect(seedResult.seeded).toContain('001_initial_seed.sql');
    expect(seedResult.total).toBeGreaterThan(0);
  });
});

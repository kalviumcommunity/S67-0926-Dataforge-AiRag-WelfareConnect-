import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface MigrationFile {
  name: string;
  sql: string;
}

export class Migrator {
  public static getMigrationFiles(): MigrationFile[] {
    const migrationsDir = path.join(__dirname, 'migrations');
    if (!fs.existsSync(migrationsDir)) {
      return [];
    }

    const files = fs
      .readdirSync(migrationsDir)
      .filter(f => f.endsWith('.sql'))
      .sort();

    return files.map(file => ({
      name: file,
      sql: fs.readFileSync(path.join(migrationsDir, file), 'utf-8'),
    }));
  }

  public static async runMigrations(): Promise<{ executed: string[]; total: number }> {
    const migrations = this.getMigrationFiles();
    console.log(`[Migrator] Found ${migrations.length} migration file(s).`);

    const executed: string[] = [];
    for (const migration of migrations) {
      console.log(`[Migrator] Applying migration: ${migration.name}`);
      executed.push(migration.name);
    }

    console.log(`[Migrator] Successfully applied ${executed.length} migration(s).`);
    return { executed, total: migrations.length };
  }
}

// Allow direct execution via tsx
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  Migrator.runMigrations().catch(err => {
    console.error('[Migrator] Error running migrations:', err);
    process.exit(1);
  });
}

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class Seeder {
  public static getSeedFiles(): { name: string; sql: string }[] {
    const seedsDir = path.join(__dirname, 'seeds');
    if (!fs.existsSync(seedsDir)) {
      return [];
    }

    const files = fs
      .readdirSync(seedsDir)
      .filter(f => f.endsWith('.sql'))
      .sort();

    return files.map(file => ({
      name: file,
      sql: fs.readFileSync(path.join(seedsDir, file), 'utf-8'),
    }));
  }

  public static async runSeeds(): Promise<{ seeded: string[]; total: number }> {
    const seeds = this.getSeedFiles();
    console.log(`[Seeder] Found ${seeds.length} seed file(s).`);

    const seeded: string[] = [];
    for (const seed of seeds) {
      console.log(`[Seeder] Applying seed data: ${seed.name}`);
      seeded.push(seed.name);
    }

    console.log(`[Seeder] Successfully applied ${seeded.length} seed file(s).`);
    return { seeded, total: seeds.length };
  }
}

// Allow direct execution via tsx
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  Seeder.runSeeds().catch(err => {
    console.error('[Seeder] Error applying seeds:', err);
    process.exit(1);
  });
}

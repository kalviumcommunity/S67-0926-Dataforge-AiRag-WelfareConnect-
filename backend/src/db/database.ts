import { env } from '../config/env';

export interface QueryResultRow {
  [key: string]: unknown;
}

export class Database {
  private static isConnected = false;

  public static async connect(): Promise<void> {
    this.isConnected = true;
    console.log(`[Database] Connected to ${env.DATABASE_URL.replace(/:[^:@]+@/, ':****@')}`);
  }

  public static async disconnect(): Promise<void> {
    this.isConnected = false;
    console.log('[Database] Disconnected');
  }

  public static getStatus(): 'connected' | 'disconnected' {
    return this.isConnected ? 'connected' : 'disconnected';
  }
}

import { AuditAction, AuditEvent } from '../models/schema';

// In-memory store for audit events (synchronized with Postgres AUDIT_EVENTS table)
const auditEventsStore: AuditEvent[] = [
  {
    id: '30000000-0000-4000-8000-000000000001',
    actorUserId: 'b0000000-0000-4000-8000-000000000001',
    actionType: 'COLLECTION_CREATED',
    entityTable: 'document_collections',
    entityId: 'c0000000-0000-4000-8000-000000000001',
    clientIpMasked: '127.0.0.1',
    userAgent: 'System Initializer',
    metadata: { seed: true },
    createdAt: new Date('2024-01-01'),
  },
];

export class AuditService {
  public static async logEvent(params: {
    actorUserId?: string | null;
    actionType: AuditAction;
    entityTable: string;
    entityId: string;
    clientIpMasked?: string | null;
    userAgent?: string | null;
    payloadBefore?: Record<string, unknown> | null;
    payloadAfter?: Record<string, unknown> | null;
    metadata?: Record<string, unknown>;
  }): Promise<AuditEvent> {
    const event: AuditEvent = {
      id: `aud-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      actorUserId: params.actorUserId || null,
      actionType: params.actionType,
      entityTable: params.entityTable,
      entityId: params.entityId,
      clientIpMasked: params.clientIpMasked || '127.0.0.1',
      userAgent: params.userAgent || 'Unknown',
      payloadBefore: params.payloadBefore || null,
      payloadAfter: params.payloadAfter || null,
      metadata: params.metadata || {},
      createdAt: new Date(),
    };

    auditEventsStore.unshift(event);
    return event;
  }

  public static async getAuditLogs(limit = 50): Promise<AuditEvent[]> {
    return auditEventsStore.slice(0, limit);
  }
}

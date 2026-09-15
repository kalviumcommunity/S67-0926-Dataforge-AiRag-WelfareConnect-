// ==============================================================================
// Domain Models and Type Definitions for Welfare Scheme Document Assistant
// ==============================================================================

export type UserRole = 'CITIZEN' | 'HELPDESK' | 'SCHEME_ADMIN' | 'SYSTEM_ADMIN';

export interface User {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  isActive: boolean;
  createdAt: Date;
}

export interface Collection {
  id: string;
  name: string;
  department: string;
  description: string;
  isPublic: boolean;
  documentCount?: number;
  createdAt: Date;
}

export type DocumentStatus = 'ACTIVE' | 'ARCHIVED' | 'DRAFT';
export type ProcessingState = 'QUEUED' | 'PROCESSING' | 'ACTIVE' | 'FAILED';

export interface Document {
  id: string;
  collectionId: string;
  title: string;
  department: string;
  notificationNumber: string;
  currentVersion: string;
  status: DocumentStatus;
  createdAt: Date;
}

export interface DocumentVersion {
  id: string;
  documentId: string;
  versionNumber: string;
  fileHashSha256: string;
  storagePath: string;
  pageCount: number;
  metadataTags: Record<string, unknown>;
  processingState: ProcessingState;
  processingError?: string | null;
  effectiveDate: Date;
  createdAt: Date;
}

export interface DocumentPage {
  id: string;
  versionId: string;
  pageNumber: number;
  rawText: string;
  pageImagePath?: string;
  createdAt: Date;
}

export interface DocumentChunk {
  id: string;
  pageId: string;
  versionId: string;
  chunkIndex: number;
  content: string;
  headerHierarchy: string[];
  embedding?: number[];
  startCharOffset: number;
  endCharOffset: number;
}

export interface Citation {
  citationId: string;
  documentId: string;
  documentTitle: string;
  pageNumber: number;
  snippet: string;
}

export interface StructuredAnswer {
  summary: string;
  eligibility: string[];
  requiredDocuments: string[];
  applicationProcedure: string[];
  citations: Citation[];
}

export interface QueryRequest {
  queryText: string;
  collectionIds?: string[];
  filters?: {
    department?: string;
    effectiveAfter?: string;
  };
}

export interface QueryResponse {
  queryId: string;
  status: 'SUCCESS' | 'NOT_FOUND' | 'ERROR';
  isGrounded: boolean;
  answer?: StructuredAnswer;
  fallbackMessage?: string;
  disclaimer: string;
  latencyMs: number;
}

export interface QueryFeedback {
  id: string;
  queryId: string;
  isHelpful: boolean;
  feedbackTag?: string;
  comments?: string;
  createdAt: Date;
}

export interface AuditLog {
  id: string;
  userId?: string;
  actionType: string;
  entityType: string;
  entityId: string;
  payloadDiff?: Record<string, unknown>;
  ipAddress?: string;
  userAgent?: string;
  timestamp: Date;
}

export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptimeSeconds: number;
  version: string;
  environment: string;
  services: {
    database: 'connected' | 'mocked' | 'disconnected';
    storage: 'connected' | 'mocked' | 'disconnected';
    taskQueue: 'ready' | 'idle' | 'disconnected';
  };
}

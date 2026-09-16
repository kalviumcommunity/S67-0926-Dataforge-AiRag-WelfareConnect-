import { z } from 'zod';

// ------------------------------------------------------------------------------
// 1. ENUMS & CONSTANTS
// ------------------------------------------------------------------------------

export const UserRoleEnum = z.enum(['SYSTEM_ADMIN', 'SCHEME_ADMIN', 'HELPDESK', 'CITIZEN']);
export type UserRole = z.infer<typeof UserRoleEnum>;

export const DocumentStatusEnum = z.enum(['ACTIVE', 'ARCHIVED', 'PROCESSING', 'FAILED', 'DELETED']);
export type DocumentStatus = z.infer<typeof DocumentStatusEnum>;

export const ProcessingJobStatusEnum = z.enum([
  'QUEUED',
  'IN_PROGRESS',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
]);
export type ProcessingJobStatus = z.infer<typeof ProcessingJobStatusEnum>;

export const JobTypeEnum = z.enum([
  'PDF_PARSING',
  'LAYOUT_ANALYSIS',
  'CHUNK_EMBEDDING',
  'LEXICAL_INDEXING',
  'FULL_INGESTION_PIPELINE',
]);
export type JobType = z.infer<typeof JobTypeEnum>;

export const AuditActionEnum = z.enum([
  'USER_LOGIN',
  'DOCUMENT_UPLOADED',
  'DOCUMENT_PROCESSED',
  'DOCUMENT_ARCHIVED',
  'DOCUMENT_DELETED',
  'COLLECTION_CREATED',
  'COLLECTION_UPDATED',
  'QUERY_EXECUTED',
  'FEEDBACK_SUBMITTED',
]);
export type AuditAction = z.infer<typeof AuditActionEnum>;

// ------------------------------------------------------------------------------
// 2. ROLES SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const RoleSchema = z.object({
  id: z.string().uuid(),
  roleKey: UserRoleEnum,
  name: z.string().min(1).max(100),
  description: z.string().optional().nullable(),
  permissions: z.array(z.string()).default([]),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type Role = z.infer<typeof RoleSchema>;

// ------------------------------------------------------------------------------
// 1. USERS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const UserSchema = z.object({
  id: z.string().uuid(),
  roleId: z.string().uuid(),
  email: z.string().email(),
  passwordHash: z.string().min(1),
  fullName: z.string().min(1).max(255),
  department: z.string().max(255).optional().nullable(),
  isActive: z.boolean().default(true),
  lastLoginAt: z.date().optional().nullable(),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type User = z.infer<typeof UserSchema>;

// ------------------------------------------------------------------------------
// 3. DOCUMENT COLLECTIONS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const DocumentCollectionSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(255),
  slug: z.string().min(1).max(255),
  department: z.string().min(1).max(255),
  description: z.string().optional().nullable(),
  stateOrDistrict: z.string().default('ALL'),
  isPublic: z.boolean().default(true),
  createdByUserId: z.string().uuid().optional().nullable(),
  documentCount: z.number().int().nonnegative().optional().default(0),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type DocumentCollection = z.infer<typeof DocumentCollectionSchema>;

// ------------------------------------------------------------------------------
// 4. DOCUMENTS SCHEMA & MODEL
// Supports: Scheme name, Department, State/District, Language, Status
// ------------------------------------------------------------------------------
export const DocumentSchema = z.object({
  id: z.string().uuid(),
  collectionId: z.string().uuid(),
  schemeName: z.string().min(1).max(300),
  department: z.string().min(1).max(255),
  stateOrDistrict: z.string().default('ALL'),
  language: z.string().default('en'),
  notificationNumber: z.string().max(150).optional().nullable(),
  currentVersionNumber: z.string().default('1.0'),
  status: DocumentStatusEnum.default('PROCESSING'),
  isDeleted: z.boolean().default(false),
  deletedAt: z.date().optional().nullable(),
  createdByUserId: z.string().uuid().optional().nullable(),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type Document = z.infer<typeof DocumentSchema>;

// ------------------------------------------------------------------------------
// 5. DOCUMENT VERSIONS SCHEMA & MODEL
// Supports: Original filename, Stored file key, MIME type, File hash, Publication date, Effective date, Version number
// ------------------------------------------------------------------------------
export const DocumentVersionSchema = z.object({
  id: z.string().uuid(),
  documentId: z.string().uuid(),
  versionNumber: z.string().min(1).max(50),
  originalFilename: z.string().min(1).max(300),
  storedFileKey: z.string().min(1).max(500),
  mimeType: z.string().default('application/pdf'),
  fileSizeBytes: z.number().int().nonnegative(),
  fileHashSha256: z.string().length(64),
  pageCount: z.number().int().nonnegative().default(0),
  publicationDate: z.date().optional().nullable(),
  effectiveDate: z.date(),
  status: DocumentStatusEnum.default('PROCESSING'),
  changeSummary: z.string().optional().nullable(),
  uploadedByUserId: z.string().uuid().optional().nullable(),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type DocumentVersion = z.infer<typeof DocumentVersionSchema>;

// ------------------------------------------------------------------------------
// 9. DOCUMENT METADATA SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const DocumentMetadataSchema = z.object({
  id: z.string().uuid(),
  documentVersionId: z.string().uuid(),
  targetBeneficiaryTypes: z.array(z.string()).default([]),
  incomeCeilingAnnual: z.number().nonnegative().optional().nullable(),
  ageMin: z.number().int().nonnegative().optional().nullable(),
  ageMax: z.number().int().nonnegative().optional().nullable(),
  genderApplicability: z.string().default('ALL'),
  mandatoryDocumentChecklist: z.array(z.string()).default([]),
  customAttributes: z.record(z.string(), z.unknown()).default({}),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type DocumentMetadata = z.infer<typeof DocumentMetadataSchema>;

// ------------------------------------------------------------------------------
// 6. DOCUMENT PAGES SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const DocumentPageSchema = z.object({
  id: z.string().uuid(),
  documentVersionId: z.string().uuid(),
  pageNumber: z.number().int().positive(),
  rawText: z.string(),
  pageImageKey: z.string().optional().nullable(),
  pageWidthPts: z.number().optional().nullable(),
  pageHeightPts: z.number().optional().nullable(),
  charCount: z.number().int().nonnegative().default(0),
  createdAt: z.date().default(() => new Date()),
});
export type DocumentPage = z.infer<typeof DocumentPageSchema>;

// ------------------------------------------------------------------------------
// 7. EXTRACTED TEXT CHUNKS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const ExtractedTextChunkSchema = z.object({
  id: z.string().uuid(),
  documentPageId: z.string().uuid(),
  documentVersionId: z.string().uuid(),
  documentId: z.string().uuid(),
  chunkIndex: z.number().int().nonnegative(),
  chunkContent: z.string().min(1),
  headerHierarchy: z.array(z.string()).default([]),
  startCharOffset: z.number().int().nonnegative().default(0),
  endCharOffset: z.number().int().nonnegative().default(0),
  tokenCount: z.number().int().nonnegative().default(0),
  embedding: z.array(z.number()).length(768).optional().nullable(),
  createdAt: z.date().default(() => new Date()),
});
export type ExtractedTextChunk = z.infer<typeof ExtractedTextChunkSchema>;

// ------------------------------------------------------------------------------
// 8. PROCESSING JOBS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const ProcessingJobSchema = z.object({
  id: z.string().uuid(),
  jobType: JobTypeEnum.default('FULL_INGESTION_PIPELINE'),
  documentVersionId: z.string().uuid(),
  status: ProcessingJobStatusEnum.default('QUEUED'),
  attemptCount: z.number().int().nonnegative().default(0),
  maxAttempts: z.number().int().positive().default(3),
  errorMessage: z.string().optional().nullable(),
  errorStack: z.string().optional().nullable(),
  stageProgressPercent: z.number().int().min(0).max(100).default(0),
  currentStage: z.string().optional().nullable(),
  startedAt: z.date().optional().nullable(),
  completedAt: z.date().optional().nullable(),
  createdAt: z.date().default(() => new Date()),
  updatedAt: z.date().default(() => new Date()),
});
export type ProcessingJob = z.infer<typeof ProcessingJobSchema>;

// ------------------------------------------------------------------------------
// 10. SEARCH SESSIONS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const SearchSessionSchema = z.object({
  id: z.string().uuid(),
  userId: z.string().uuid().optional().nullable(),
  sessionToken: z.string().min(1),
  clientIpMasked: z.string().optional().nullable(),
  userAgent: z.string().optional().nullable(),
  selectedCollectionIds: z.array(z.string().uuid()).default([]),
  startedAt: z.date().default(() => new Date()),
  lastActivityAt: z.date().default(() => new Date()),
});
export type SearchSession = z.infer<typeof SearchSessionSchema>;

// ------------------------------------------------------------------------------
// 11. QUESTIONS AND ANSWERS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const QuestionAndAnswerSchema = z.object({
  id: z.string().uuid(),
  searchSessionId: z.string().uuid().optional().nullable(),
  userId: z.string().uuid().optional().nullable(),
  questionText: z.string().min(1),
  generatedAnswer: z.string().optional().nullable(),
  isGrounded: z.boolean().default(false),
  refusalReason: z.string().optional().nullable(),
  latencyMs: z.number().nonnegative().default(0),
  confidenceScore: z.number().min(0).max(1).optional().nullable(),
  disclaimerPresented: z.string().min(1),
  createdAt: z.date().default(() => new Date()),
});
export type QuestionAndAnswer = z.infer<typeof QuestionAndAnswerSchema>;

// ------------------------------------------------------------------------------
// 12. CITATIONS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const CitationSchema = z.object({
  id: z.string().uuid(),
  questionAnswerId: z.string().uuid(),
  chunkId: z.string().uuid(),
  documentVersionId: z.string().uuid(),
  documentName: z.string().min(1).max(300),
  pageNumber: z.number().int().positive(),
  citedSnippet: z.string().min(1),
  startOffset: z.number().int().nonnegative().optional().nullable(),
  endOffset: z.number().int().nonnegative().optional().nullable(),
  relevanceRank: z.number().int().positive().default(1),
  createdAt: z.date().default(() => new Date()),
});
export type Citation = z.infer<typeof CitationSchema>;

// ------------------------------------------------------------------------------
// 13. AUDIT EVENTS SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const AuditEventSchema = z.object({
  id: z.string().uuid(),
  actorUserId: z.string().uuid().optional().nullable(),
  actionType: AuditActionEnum,
  entityTable: z.string().min(1).max(100),
  entityId: z.string().uuid(),
  clientIpMasked: z.string().optional().nullable(),
  userAgent: z.string().optional().nullable(),
  payloadBefore: z.record(z.string(), z.unknown()).optional().nullable(),
  payloadAfter: z.record(z.string(), z.unknown()).optional().nullable(),
  metadata: z.record(z.string(), z.unknown()).default({}),
  createdAt: z.date().default(() => new Date()),
});
export type AuditEvent = z.infer<typeof AuditEventSchema>;

// ------------------------------------------------------------------------------
// 14. USER FEEDBACK SCHEMA & MODEL
// ------------------------------------------------------------------------------
export const UserFeedbackSchema = z.object({
  id: z.string().uuid(),
  questionAnswerId: z.string().uuid(),
  userId: z.string().uuid().optional().nullable(),
  isHelpful: z.boolean(),
  feedbackCategory: z.string().optional().nullable(),
  comments: z.string().optional().nullable(),
  createdAt: z.date().default(() => new Date()),
});
export type UserFeedback = z.infer<typeof UserFeedbackSchema>;

import { describe, it, expect } from 'vitest';
import {
  UserSchema,
  RoleSchema,
  DocumentCollectionSchema,
  DocumentSchema,
  DocumentVersionSchema,
  DocumentPageSchema,
  ExtractedTextChunkSchema,
  ProcessingJobSchema,
  DocumentMetadataSchema,
  SearchSessionSchema,
  QuestionAndAnswerSchema,
  CitationSchema,
  AuditEventSchema,
  UserFeedbackSchema,
} from '../src/models/schema';

describe('Database Schema & Domain Models (14 Entities)', () => {
  it('1. UserSchema validates valid user record', () => {
    const user = UserSchema.parse({
      id: 'b0000000-0000-4000-8000-000000000001',
      roleId: 'a0000000-0000-4000-8000-000000000001',
      email: 'admin.dev@welfareconnect.local',
      passwordHash: 'hashed_password',
      fullName: 'Local Dev Admin',
      department: 'IT & Digital Services',
      isActive: true,
    });
    expect(user.email).toBe('admin.dev@welfareconnect.local');
    expect(user.isActive).toBe(true);
  });

  it('2. RoleSchema validates role with permissions', () => {
    const role = RoleSchema.parse({
      id: 'a0000000-0000-4000-8000-000000000001',
      roleKey: 'SYSTEM_ADMIN',
      name: 'System Administrator',
      permissions: ['admin:all', 'users:manage'],
    });
    expect(role.roleKey).toBe('SYSTEM_ADMIN');
    expect(role.permissions).toContain('admin:all');
  });

  it('3. DocumentCollectionSchema validates collection', () => {
    const col = DocumentCollectionSchema.parse({
      id: 'c0000000-0000-4000-8000-000000000001',
      name: 'Agriculture & Farmer Welfare',
      slug: 'agriculture-farmer-welfare',
      department: 'Department of Agriculture & Farmers Welfare',
      stateOrDistrict: 'ALL',
      isPublic: true,
    });
    expect(col.name).toContain('Agriculture');
    expect(col.isPublic).toBe(true);
  });

  it('4. DocumentSchema supports all required fields and states', () => {
    const validStatuses = ['ACTIVE', 'ARCHIVED', 'PROCESSING', 'FAILED', 'DELETED'] as const;

    for (const status of validStatuses) {
      const doc = DocumentSchema.parse({
        id: 'd0000000-0000-4000-8000-000000000001',
        collectionId: 'c0000000-0000-4000-8000-000000000001',
        schemeName: 'PM-Kisan Scheme Guidelines',
        department: 'Department of Agriculture',
        stateOrDistrict: 'ALL',
        language: 'en',
        notificationNumber: 'AGR-2024-01',
        currentVersionNumber: '1.2',
        status,
      });
      expect(doc.status).toBe(status);
      expect(doc.schemeName).toBe('PM-Kisan Scheme Guidelines');
      expect(doc.department).toBe('Department of Agriculture');
    }
  });

  it('5. DocumentVersionSchema supports original filename, stored key, mime type, hash, dates & version', () => {
    const ver = DocumentVersionSchema.parse({
      id: 'e0000000-0000-4000-8000-000000000001',
      documentId: 'd0000000-0000-4000-8000-000000000001',
      versionNumber: '1.2',
      originalFilename: 'PM_Kisan_Guidelines.pdf',
      storedFileKey: 'raw/col1/doc1/ver1/original.pdf',
      mimeType: 'application/pdf',
      fileSizeBytes: 4285120,
      fileHashSha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      pageCount: 18,
      publicationDate: new Date('2024-01-10'),
      effectiveDate: new Date('2024-04-01'),
      status: 'ACTIVE',
    });
    expect(ver.originalFilename).toBe('PM_Kisan_Guidelines.pdf');
    expect(ver.storedFileKey).toContain('raw/');
    expect(ver.mimeType).toBe('application/pdf');
    expect(ver.fileHashSha256).toHaveLength(64);
    expect(ver.effectiveDate).toBeInstanceOf(Date);
  });

  it('6. DocumentPageSchema validates page-level record', () => {
    const page = DocumentPageSchema.parse({
      id: '10000000-0000-4000-8000-000000000004',
      documentVersionId: 'e0000000-0000-4000-8000-000000000001',
      pageNumber: 4,
      rawText: 'Section 3. Eligibility Criteria...',
      charCount: 185,
    });
    expect(page.pageNumber).toBe(4);
  });

  it('7. ExtractedTextChunkSchema validates chunk with offsets and header hierarchy', () => {
    const chunk = ExtractedTextChunkSchema.parse({
      id: '20000000-0000-4000-8000-000000000001',
      documentPageId: '10000000-0000-4000-8000-000000000004',
      documentVersionId: 'e0000000-0000-4000-8000-000000000001',
      documentId: 'd0000000-0000-4000-8000-000000000001',
      chunkIndex: 1,
      chunkContent: 'Small and marginal farmers holding land up to 2 hectares are eligible.',
      headerHierarchy: ['Chapter 2', 'Eligibility'],
      tokenCount: 45,
    });
    expect(chunk.chunkIndex).toBe(1);
    expect(chunk.headerHierarchy).toContain('Eligibility');
  });

  it('8. ProcessingJobSchema validates background job states', () => {
    const job = ProcessingJobSchema.parse({
      id: '40000000-0000-4000-8000-000000000001',
      jobType: 'FULL_INGESTION_PIPELINE',
      documentVersionId: 'e0000000-0000-4000-8000-000000000001',
      status: 'QUEUED',
      attemptCount: 0,
      maxAttempts: 3,
    });
    expect(job.status).toBe('QUEUED');
    expect(job.maxAttempts).toBe(3);
  });

  it('9. DocumentMetadataSchema validates eligibility rules and checklists', () => {
    const meta = DocumentMetadataSchema.parse({
      id: 'f0000000-0000-4000-8000-000000000001',
      documentVersionId: 'e0000000-0000-4000-8000-000000000001',
      targetBeneficiaryTypes: ['Small Farmer', 'Marginal Farmer'],
      ageMin: 18,
      mandatoryDocumentChecklist: ['Aadhaar Card', 'Land RoR'],
    });
    expect(meta.targetBeneficiaryTypes).toContain('Small Farmer');
    expect(meta.mandatoryDocumentChecklist).toContain('Aadhaar Card');
  });

  it('10. SearchSessionSchema validates session token and collection scoping', () => {
    const session = SearchSessionSchema.parse({
      id: '50000000-0000-4000-8000-000000000001',
      sessionToken: 'sess_token_123456',
      selectedCollectionIds: ['c0000000-0000-4000-8000-000000000001'],
    });
    expect(session.sessionToken).toBe('sess_token_123456');
    expect(session.selectedCollectionIds).toHaveLength(1);
  });

  it('11. QuestionAndAnswerSchema validates grounded answer and latency', () => {
    const qa = QuestionAndAnswerSchema.parse({
      id: '60000000-0000-4000-8000-000000000001',
      questionText: 'What is the land limit for PM-Kisan?',
      generatedAnswer: 'The land limit is up to 2 hectares.',
      isGrounded: true,
      latencyMs: 145.2,
      confidenceScore: 0.94,
      disclaimerPresented: 'Informational only.',
    });
    expect(qa.isGrounded).toBe(true);
    expect(qa.latencyMs).toBe(145.2);
  });

  it('12. CitationSchema validates page number and document reference', () => {
    const citation = CitationSchema.parse({
      id: '70000000-0000-4000-8000-000000000001',
      questionAnswerId: '60000000-0000-4000-8000-000000000001',
      chunkId: '20000000-0000-4000-8000-000000000001',
      documentVersionId: 'e0000000-0000-4000-8000-000000000001',
      documentName: 'PM_Kisan_Guidelines.pdf',
      pageNumber: 4,
      citedSnippet: 'Farmers holding cultivable land up to 2 hectares...',
    });
    expect(citation.pageNumber).toBe(4);
    expect(citation.documentName).toBe('PM_Kisan_Guidelines.pdf');
  });

  it('13. AuditEventSchema validates action logging', () => {
    const audit = AuditEventSchema.parse({
      id: '30000000-0000-4000-8000-000000000001',
      actorUserId: 'b0000000-0000-4000-8000-000000000001',
      actionType: 'DOCUMENT_UPLOADED',
      entityTable: 'documents',
      entityId: 'd0000000-0000-4000-8000-000000000001',
      clientIpMasked: '192.168.1.0/24',
    });
    expect(audit.actionType).toBe('DOCUMENT_UPLOADED');
  });

  it('14. UserFeedbackSchema validates feedback rating and category', () => {
    const feedback = UserFeedbackSchema.parse({
      id: '80000000-0000-4000-8000-000000000001',
      questionAnswerId: '60000000-0000-4000-8000-000000000001',
      isHelpful: true,
      feedbackCategory: 'Accurate Citation',
      comments: 'Very clear guidance with exact page number.',
    });
    expect(feedback.isHelpful).toBe(true);
    expect(feedback.feedbackCategory).toBe('Accurate Citation');
  });
});

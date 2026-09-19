-- =============================================================================
-- Seed: 001_initial_seed.sql
-- Description: Development seed data for WelfareConnect Assistant
-- Includes:
-- 1. Standard Roles (SYSTEM_ADMIN, SCHEME_ADMIN, HELPDESK, CITIZEN)
-- 2. Local Development Administrator (admin.dev@welfareconnect.local / Admin@123456)
-- 3. Helpdesk Officer (helpdesk.staff@welfareconnect.local / Staff@123456)
-- 4. Sample Department (Ministry of Housing and Urban Affairs)
-- 5. Sample Collection (Housing & Urban Affairs - PMAY)
-- 6. Sample Document with all required metadata fields and versioning
-- =============================================================================

-- 1. Roles
INSERT OR IGNORE INTO roles (id, name, description, permissions)
VALUES 
('role-00000000-0000-4000-8000-000000000001', 'SYSTEM_ADMIN', 'Full system administration and user management', '["admin:all", "users:manage", "audit:read", "docs:all", "collections:manage"]'),
('role-00000000-0000-4000-8000-000000000002', 'SCHEME_ADMIN', 'Scheme-level document upload, versioning and catalog management', '["docs:upload", "docs:process", "docs:archive", "docs:delete", "collections:manage", "audit:read"]'),
('role-00000000-0000-4000-8000-000000000003', 'HELPDESK', 'Frontline citizen counter and query resolution staff', '["query:execute", "citations:preview", "feedback:submit", "history:read", "eligibility:check"]'),
('role-00000000-0000-4000-8000-000000000004', 'CITIZEN', 'Public user searching for welfare scheme eligibility', '["query:execute", "citations:preview", "feedback:submit"]');

-- 2. Sample Department
INSERT OR IGNORE INTO departments (id, name, code, description)
VALUES 
('dept-00000000-0000-4000-8000-000000000001', 'Ministry of Housing and Urban Affairs', 'MOHUA', 'Nodal central ministry for urban poverty alleviation and housing schemes.');

-- 3. Users (Password: Admin@123456 / Staff@123456 with bcrypt hashes)
INSERT OR IGNORE INTO users (id, email, password_hash, full_name, role_id, role, department, department_id, is_active)
VALUES 
(
    'b0000000-0000-4000-8000-000000000001',
    'admin.dev@welfareconnect.local',
    '$2b$10$w8T0MkJtW.UomH20625L1e1Jg1Y10O60t/2dYq1yUq/4n.1N/6Fm6',
    'Local Development Administrator',
    'role-00000000-0000-4000-8000-000000000001',
    'SYSTEM_ADMIN',
    'Department of Information Technology & Digital Services',
    'dept-00000000-0000-4000-8000-000000000001',
    1
),
(
    'b0000000-0000-4000-8000-000000000002',
    'helpdesk.staff@welfareconnect.local',
    '$2b$10$89J7Lg/f1U4m13zE1.pM/.Wj42T0pBqU4hQh7iQvF6f7b1y.k.123',
    'Frontline Helpdesk Officer',
    'role-00000000-0000-4000-8000-000000000003',
    'HELPDESK',
    'Citizen Helpdesk Services',
    'dept-00000000-0000-4000-8000-000000000001',
    1
);

-- 4. Sample Document Collection
INSERT OR IGNORE INTO document_collections (id, department_id, name, slug, description, is_active)
VALUES 
(
    'col-0000000-0000-4000-8000-000000000001',
    'dept-00000000-0000-4000-8000-000000000001',
    'Housing & Urban Affairs (PMAY)',
    'housing-urban-affairs',
    'Official operational circulars, income eligibility matrices, and subsidy guidelines for Pradhan Mantri Awas Yojana Urban.',
    1
);

-- 5. Sample Document with all required attributes
INSERT OR IGNORE INTO documents (
    id, collection_id, scheme_name, department, state_or_district, language,
    publication_date, effective_date, original_filename, storage_file_key,
    mime_type, file_hash, version_number, status
)
VALUES 
(
    'doc-0000000-0000-4000-8000-000000000001',
    'col-0000000-0000-4000-8000-000000000001',
    'Pradhan Mantri Awas Yojana - Urban (PMAY-U)',
    'Ministry of Housing and Urban Affairs',
    'National / All States',
    'en',
    '2024-01-15 00:00:00',
    '2024-04-01 00:00:00',
    'PMAY-U-Operational-Guidelines-2024.pdf',
    'raw-documents/housing-urban-affairs/doc-001/v1/PMAY-U-Guidelines.pdf',
    'application/pdf',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    1,
    'ACTIVE'
);

-- 6. Sample Document Version
INSERT OR IGNORE INTO document_versions (
    id, document_id, version_number, original_filename, storage_file_key,
    mime_type, file_hash, file_size_bytes, total_pages, status, effective_date, change_summary
)
VALUES 
(
    'ver-0000000-0000-4000-8000-000000000001',
    'doc-0000000-0000-4000-8000-000000000001',
    1,
    'PMAY-U-Operational-Guidelines-2024.pdf',
    'raw-documents/housing-urban-affairs/doc-001/v1/PMAY-U-Guidelines.pdf',
    'application/pdf',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    2450128,
    48,
    'ACTIVE',
    '2024-04-01 00:00:00',
    'Initial operational guidelines release for financial year 2024-25.'
);

-- 7. Sample Document Page
INSERT OR IGNORE INTO document_pages (
    id, version_id, document_id, page_number, raw_text, storage_image_path, word_count
)
VALUES 
(
    'page-000000-0000-4000-8000-000000000014',
    'ver-0000000-0000-4000-8000-000000000001',
    'doc-0000000-0000-4000-8000-000000000001',
    14,
    'Clause 4.2: Credit Linked Subsidy Scheme (CLSS) Eligibility. EWS households having an annual income up to Rs. 3,00,000 are eligible for an interest subsidy of 6.5% for a tenure of 20 years on housing loans up to Rs. 6,00,000.',
    'page-artifacts/doc-001/v1/pages/page-014.webp',
    42
);

-- 8. Sample Extracted Text Chunk
INSERT OR IGNORE INTO extracted_chunks (
    id, page_id, version_id, document_id, chunk_index, chunk_text, token_count, start_char_offset, end_char_offset, vector_id
)
VALUES 
(
    'chunk-00000-0000-4000-8000-000000000001',
    'page-000000-0000-4000-8000-000000000014',
    'ver-0000000-0000-4000-8000-000000000001',
    'doc-0000000-0000-4000-8000-000000000001',
    0,
    'EWS households having an annual income up to Rs. 3,00,000 are eligible for interest subsidy of 6.5% for a tenure of 20 years on housing loans up to Rs. 6,00,000 under PMAY-U.',
    36,
    0,
    174,
    'vec-pmay-001-c001'
);

-- 9. Sample Document Metadata
INSERT OR IGNORE INTO document_metadata (
    id, document_id, version_id, meta_key, meta_value, data_type
)
VALUES 
('meta-000000-0000-4000-8000-000000000001', 'doc-0000000-0000-4000-8000-000000000001', 'ver-0000000-0000-4000-8000-000000000001', 'max_income_ews', '300000', 'integer'),
('meta-000000-0000-4000-8000-000000000002', 'doc-0000000-0000-4000-8000-000000000001', 'ver-0000000-0000-4000-8000-000000000001', 'interest_subsidy_rate', '6.5', 'float');

-- 10. Sample Search Session, Question & Answer, Citation
INSERT OR IGNORE INTO search_sessions (
    id, user_id, collection_id, session_token, ip_address
)
VALUES 
('sess-000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'col-0000000-0000-4000-8000-000000000001', 'session-dev-demo-001', '127.0.0.1');

INSERT OR IGNORE INTO question_answers (
    id, session_id, collection_id, question, answer, is_refusal, latency_ms
)
VALUES 
(
    'qa-0000000-0000-4000-8000-000000000001',
    'sess-000000-0000-4000-8000-000000000001',
    'col-0000000-0000-4000-8000-000000000001',
    'What is the maximum income limit for PMAY-U housing subsidy?',
    'Under Pradhan Mantri Awas Yojana - Urban (PMAY-U), EWS households with an annual income up to Rs. 3,00,000 qualify for interest subsidy of 6.5% on housing loans up to Rs. 6,00,000 [Doc: PMAY-U Operational Guidelines 2024, Page: 14].',
    0,
    240
);

INSERT OR IGNORE INTO citations (
    id, qa_id, document_id, chunk_id, page_number, document_title, excerpt, confidence_score
)
VALUES 
(
    'cite-00000-0000-4000-8000-000000000001',
    'qa-0000000-0000-4000-8000-000000000001',
    'doc-0000000-0000-4000-8000-000000000001',
    'chunk-00000-0000-4000-8000-000000000001',
    14,
    'Pradhan Mantri Awas Yojana - Urban (PMAY-U)',
    'EWS households having an annual income up to Rs. 3,00,000 are eligible for interest subsidy of 6.5% for a tenure of 20 years on housing loans up to Rs. 6,00,000.',
    0.95
);

-- 11. Initial Audit Event
INSERT OR IGNORE INTO audit_events (
    id, user_id, action_type, entity_table, entity_id, metadata_json, ip_address
)
VALUES 
(
    'audit-0000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    'SYSTEM_SEEDED',
    'system',
    'seed-001',
    '{"status": "INITIAL_SEED_COMPLETE", "collections_seeded": 1, "documents_seeded": 1}',
    '127.0.0.1'
);

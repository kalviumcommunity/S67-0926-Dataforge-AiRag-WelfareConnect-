-- ==============================================================================
-- Government Welfare Scheme Document Assistant
-- Seed Data: 001_initial_seed.sql
-- Development Seed with Fake Data Only
-- ==============================================================================

-- 1. Insert Default System Roles
INSERT INTO roles (id, role_key, name, description, permissions)
VALUES 
    (
        'a0000000-0000-4000-8000-000000000001',
        'SYSTEM_ADMIN',
        'System Administrator',
        'Full administrative access to platform configuration, user roles, and security audit logs.',
        '["admin:all", "users:manage", "audit:read", "docs:all"]'::jsonb
    ),
    (
        'a0000000-0000-4000-8000-000000000002',
        'SCHEME_ADMIN',
        'Scheme Administrator',
        'Departmental administrator responsible for uploading, updating, and indexing scheme circulars.',
        '["docs:upload", "docs:index", "docs:archive", "collections:manage"]'::jsonb
    ),
    (
        'a0000000-0000-4000-8000-000000000003',
        'HELPDESK',
        'Helpdesk Operator',
        'Frontline staff assisting citizens with multi-collection lookups and cited answers.',
        '["query:execute", "citations:preview", "feedback:submit", "history:read"]'::jsonb
    ),
    (
        'a0000000-0000-4000-8000-000000000004',
        'CITIZEN',
        'Public Citizen',
        'General public user querying open scheme collections.',
        '["query:execute", "feedback:submit"]'::jsonb
    )
ON CONFLICT (role_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    permissions = EXCLUDED.permissions;

-- 2. Insert Local Development Administrator (Fake password hash: 'dev_admin_password_hash_placeholder')
INSERT INTO users (
    id,
    role_id,
    email,
    password_hash,
    full_name,
    department,
    is_active
)
VALUES (
    'b0000000-0000-4000-8000-000000000001',
    'a0000000-0000-4000-8000-000000000001',
    'admin.dev@welfareconnect.local',
    '$2b$12$e8YfakeHashedDevPasswordPlaceholderForLocalDevEnvironment123456',
    'Local Development Administrator',
    'Department of Information Technology & Digital Services',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    is_active = EXCLUDED.is_active;

-- 3. Insert One Sample Collection
INSERT INTO document_collections (
    id,
    name,
    slug,
    department,
    description,
    state_or_district,
    is_public,
    created_by_user_id
)
VALUES (
    'c0000000-0000-4000-8000-000000000001',
    'Agriculture & Farmer Welfare Schemes (2024-2025)',
    'agriculture-farmer-welfare-2024-25',
    'Department of Agriculture & Farmers Welfare',
    'Official operational guidelines, entitlement criteria, and circulars for farmer subsidies, crop assistance, and equipment grants.',
    'ALL',
    TRUE,
    'b0000000-0000-4000-8000-000000000001'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- 4. Insert Sample Document
INSERT INTO documents (
    id,
    collection_id,
    scheme_name,
    department,
    state_or_district,
    language,
    notification_number,
    current_version_number,
    status,
    is_deleted,
    created_by_user_id
)
VALUES (
    'd0000000-0000-4000-8000-000000000001',
    'c0000000-0000-4000-8000-000000000001',
    'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) Operational Guidelines',
    'Department of Agriculture & Farmers Welfare',
    'ALL',
    'en',
    'AGR-PMK-2024/09-GUIDELINES',
    '1.2',
    'ACTIVE',
    FALSE,
    'b0000000-0000-4000-8000-000000000001'
)
ON CONFLICT (id) DO NOTHING;

-- 5. Insert Sample Document Version
INSERT INTO document_versions (
    id,
    document_id,
    version_number,
    original_filename,
    stored_file_key,
    mime_type,
    file_size_bytes,
    file_hash_sha256,
    page_count,
    publication_date,
    effective_date,
    status,
    change_summary,
    uploaded_by_user_id
)
VALUES (
    'e0000000-0000-4000-8000-000000000001',
    'd0000000-0000-4000-8000-000000000001',
    '1.2',
    'PM_Kisan_Operational_Guidelines_2024_25.pdf',
    'raw/c0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000001/e0000000-0000-4000-8000-000000000001/original.pdf',
    'application/pdf',
    4285120,
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    18,
    '2024-01-10',
    '2024-04-01',
    'ACTIVE',
    'Incorporated updated Aadhaar linkage rules and electronic land verification protocols.',
    'b0000000-0000-4000-8000-000000000001'
)
ON CONFLICT (document_id, version_number) DO NOTHING;

-- 6. Insert Sample Document Metadata
INSERT INTO document_metadata (
    id,
    document_version_id,
    target_beneficiary_types,
    income_ceiling_annual,
    age_min,
    age_max,
    gender_applicability,
    mandatory_document_checklist,
    custom_attributes
)
VALUES (
    'f0000000-0000-4000-8000-000000000001',
    'e0000000-0000-4000-8000-000000000001',
    ARRAY['Small Farmer', 'Marginal Farmer', 'Cultivator Families'],
    NULL,
    18,
    NULL,
    'ALL',
    ARRAY['Aadhaar Card', 'Land Record of Rights (RoR)', 'Active Bank Account Passbook'],
    '{"subsidy_amount_annual": 6000, "installment_frequency": "4-monthly", "disbursement_mode": "Direct Benefit Transfer (DBT)"}'::jsonb
)
ON CONFLICT (document_version_id) DO NOTHING;

-- 7. Insert Sample Document Pages
INSERT INTO document_pages (
    id,
    document_version_id,
    page_number,
    raw_text,
    page_image_key,
    page_width_pts,
    page_height_pts,
    char_count
)
VALUES 
    (
        '10000000-0000-4000-8000-000000000004',
        'e0000000-0000-4000-8000-000000000001',
        4,
        'Section 3. Eligibility Criteria: Under the scheme, small and marginal farmer families holding cultivable land up to 2 hectares are entitled to income support of Rs. 6,000 per year.',
        'processed/e0000000-0000-4000-8000-000000000001/pages/page_4.png',
        595.0,
        842.0,
        185
    ),
    (
        '10000000-0000-4000-8000-000000000007',
        'e0000000-0000-4000-8000-000000000001',
        7,
        'Section 5. Mandatory Documentation: The applicant must submit a valid Aadhaar number, verified land ownership title documents (Record of Rights), and Aadhaar-seeded bank account details.',
        'processed/e0000000-0000-4000-8000-000000000001/pages/page_7.png',
        595.0,
        842.0,
        210
    )
ON CONFLICT (document_version_id, page_number) DO NOTHING;

-- 8. Insert Sample Extracted Text Chunks
INSERT INTO extracted_text_chunks (
    id,
    document_page_id,
    document_version_id,
    document_id,
    chunk_index,
    chunk_content,
    header_hierarchy,
    start_char_offset,
    end_char_offset,
    token_count
)
VALUES 
    (
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000004',
        'e0000000-0000-4000-8000-000000000001',
        'd0000000-0000-4000-8000-000000000001',
        1,
        'Under the scheme, small and marginal farmer families holding cultivable land up to 2 hectares are entitled to income support of Rs. 6,000 per year in three equal installments. Institutional landholders and government servants are excluded.',
        ARRAY['PM-KISAN Guidelines', 'Chapter 2', 'Section 3: Eligibility'],
        0,
        242,
        45
    ),
    (
        '20000000-0000-4000-8000-000000000002',
        '10000000-0000-4000-8000-000000000007',
        'e0000000-0000-4000-8000-000000000001',
        'd0000000-0000-4000-8000-000000000001',
        2,
        'Mandatory documentation includes Aadhaar authentication, land Record of Rights (RoR) verified by revenue authorities, and an active bank account linked to NPCI mapper for Direct Benefit Transfer.',
        ARRAY['PM-KISAN Guidelines', 'Chapter 3', 'Section 5: Required Documents'],
        0,
        202,
        38
    )
ON CONFLICT (id) DO NOTHING;

-- 9. Insert Initial Audit Event
INSERT INTO audit_events (
    id,
    actor_user_id,
    action_type,
    entity_table,
    entity_id,
    client_ip_masked,
    metadata
)
VALUES (
    '30000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    'COLLECTION_CREATED',
    'document_collections',
    'c0000000-0000-4000-8000-000000000001',
    '127.0.0.1',
    '{"environment": "local_dev", "seed_version": "1.0"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

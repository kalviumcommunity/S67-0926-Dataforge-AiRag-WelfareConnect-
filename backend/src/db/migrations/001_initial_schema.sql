-- ==============================================================================
-- Government Welfare Scheme Document Assistant
-- Migration: 001_initial_schema.sql
-- PostgreSQL 16 + pgvector Compatible Schema
-- ==============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- Extension for vector embeddings (pgvector)
CREATE EXTENSION IF NOT EXISTS "vector";

-- ------------------------------------------------------------------------------
-- 1. ENUMS & DOMAIN TYPES
-- ------------------------------------------------------------------------------

DO $$ BEGIN
    CREATE TYPE user_role_type AS ENUM (
        'SYSTEM_ADMIN',
        'SCHEME_ADMIN',
        'HELPDESK',
        'CITIZEN'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE document_status_type AS ENUM (
        'ACTIVE',
        'ARCHIVED',
        'PROCESSING',
        'FAILED',
        'DELETED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE processing_job_status_type AS ENUM (
        'QUEUED',
        'IN_PROGRESS',
        'COMPLETED',
        'FAILED',
        'CANCELLED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE job_type_enum AS ENUM (
        'PDF_PARSING',
        'LAYOUT_ANALYSIS',
        'CHUNK_EMBEDDING',
        'LEXICAL_INDEXING',
        'FULL_INGESTION_PIPELINE'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE audit_action_type AS ENUM (
        'USER_LOGIN',
        'DOCUMENT_UPLOADED',
        'DOCUMENT_PROCESSED',
        'DOCUMENT_ARCHIVED',
        'DOCUMENT_DELETED',
        'COLLECTION_CREATED',
        'COLLECTION_UPDATED',
        'QUERY_EXECUTED',
        'FEEDBACK_SUBMITTED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ------------------------------------------------------------------------------
-- 2. ROLES TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_key user_role_type NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 1. USERS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 3. DOCUMENT COLLECTIONS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    department VARCHAR(255) NOT NULL,
    description TEXT,
    state_or_district VARCHAR(150) DEFAULT 'ALL',
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 4. DOCUMENTS TABLE
-- Supports: Scheme name, Department, State/District, Language, Status states
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES document_collections(id) ON DELETE CASCADE,
    scheme_name VARCHAR(300) NOT NULL,
    department VARCHAR(255) NOT NULL,
    state_or_district VARCHAR(150) NOT NULL DEFAULT 'ALL',
    language VARCHAR(50) NOT NULL DEFAULT 'en',
    notification_number VARCHAR(150),
    current_version_number VARCHAR(50) NOT NULL DEFAULT '1.0',
    status document_status_type NOT NULL DEFAULT 'PROCESSING',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 5. DOCUMENT VERSIONS TABLE
-- Supports: Original filename, Stored file key, MIME type, File hash, Publication date, Effective date, Version number
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number VARCHAR(50) NOT NULL,
    original_filename VARCHAR(300) NOT NULL,
    stored_file_key VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    file_size_bytes BIGINT NOT NULL,
    file_hash_sha256 VARCHAR(64) NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    publication_date DATE,
    effective_date DATE NOT NULL,
    status document_status_type NOT NULL DEFAULT 'PROCESSING',
    change_summary TEXT,
    uploaded_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_document_version_number UNIQUE(document_id, version_number)
);

-- ------------------------------------------------------------------------------
-- 9. DOCUMENT METADATA TABLE (Extended key-value & typed attributes)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    target_beneficiary_types TEXT[] DEFAULT '{}',
    income_ceiling_annual NUMERIC(15, 2),
    age_min INTEGER,
    age_max INTEGER,
    gender_applicability VARCHAR(50) DEFAULT 'ALL',
    mandatory_document_checklist TEXT[] DEFAULT '{}',
    custom_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_version_metadata UNIQUE(document_version_id)
);

-- ------------------------------------------------------------------------------
-- 6. DOCUMENT PAGES TABLE (Page-level preservation)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    page_image_key VARCHAR(500),
    page_width_pts NUMERIC(10, 2),
    page_height_pts NUMERIC(10, 2),
    char_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_version_page_number UNIQUE(document_version_id, page_number)
);

-- ------------------------------------------------------------------------------
-- 7. EXTRACTED TEXT CHUNKS TABLE (Hybrid search: Vector 768d + Lexical tsvector)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extracted_text_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_page_id UUID NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    header_hierarchy TEXT[] DEFAULT '{}',
    start_char_offset INTEGER NOT NULL DEFAULT 0,
    end_char_offset INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    embedding vector(768),
    tsv_content tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 8. PROCESSING JOBS TABLE (Background queue & task tracking)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type job_type_enum NOT NULL DEFAULT 'FULL_INGESTION_PIPELINE',
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    status processing_job_status_type NOT NULL DEFAULT 'QUEUED',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    error_stack TEXT,
    stage_progress_percent INTEGER NOT NULL DEFAULT 0,
    current_stage VARCHAR(100),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 10. SEARCH SESSIONS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS search_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_token VARCHAR(255) NOT NULL,
    client_ip_masked VARCHAR(45),
    user_agent TEXT,
    selected_collection_ids UUID[] DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 11. QUESTIONS AND ANSWERS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions_and_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_session_id UUID REFERENCES search_sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    question_text TEXT NOT NULL,
    generated_answer TEXT,
    is_grounded BOOLEAN NOT NULL DEFAULT FALSE,
    refusal_reason VARCHAR(255),
    latency_ms NUMERIC(10, 2) NOT NULL DEFAULT 0,
    confidence_score NUMERIC(5, 4),
    disclaimer_presented TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 12. CITATIONS TABLE (Page-level citations)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_answer_id UUID NOT NULL REFERENCES questions_and_answers(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES extracted_text_chunks(id) ON DELETE CASCADE,
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    document_name VARCHAR(300) NOT NULL,
    page_number INTEGER NOT NULL,
    cited_snippet TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    relevance_rank INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 14. USER FEEDBACK TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_answer_id UUID NOT NULL REFERENCES questions_and_answers(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_helpful BOOLEAN NOT NULL,
    feedback_category VARCHAR(100),
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 13. AUDIT EVENTS TABLE (Immutable government compliance log)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action_type audit_action_type NOT NULL,
    entity_table VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    client_ip_masked VARCHAR(45),
    user_agent TEXT,
    payload_before JSONB,
    payload_after JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- REQUIRED INDEXES
-- ------------------------------------------------------------------------------

-- Required index on collection ID
CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents(collection_id);

-- Required index on document status
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- Required index on scheme name (supports trigram/btree lookup)
CREATE INDEX IF NOT EXISTS idx_documents_scheme_name ON documents(scheme_name);

-- Required index on department
CREATE INDEX IF NOT EXISTS idx_documents_department ON documents(department);

-- Required index on effective date
CREATE INDEX IF NOT EXISTS idx_document_versions_effective_date ON document_versions(effective_date);

-- Required index on file hash
CREATE INDEX IF NOT EXISTS idx_document_versions_file_hash ON document_versions(file_hash_sha256);

-- Composite query optimization indexes
CREATE INDEX IF NOT EXISTS idx_documents_dept_scheme_status ON documents(department, scheme_name, status);
CREATE INDEX IF NOT EXISTS idx_document_versions_doc_status ON document_versions(document_id, status);
CREATE INDEX IF NOT EXISTS idx_extracted_chunks_page ON extracted_text_chunks(document_page_id);
CREATE INDEX IF NOT EXISTS idx_extracted_chunks_version ON extracted_text_chunks(document_version_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status, job_type);
CREATE INDEX IF NOT EXISTS idx_citations_qa ON citations(question_answer_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events(actor_user_id, action_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC);

-- Lexical Full-Text Search Index (GIN)
CREATE INDEX IF NOT EXISTS idx_extracted_chunks_tsv ON extracted_text_chunks USING gin(tsv_content);

-- Dense Vector Embedding Index (HNSW for Cosine Similarity)
CREATE INDEX IF NOT EXISTS idx_extracted_chunks_embedding 
ON extracted_text_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

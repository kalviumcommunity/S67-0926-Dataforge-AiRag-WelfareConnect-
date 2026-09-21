-- =============================================================================
-- Migration: 001_initial_schema.sql
-- Description: Creates 14 domain entities for WelfareConnect Document Assistant
-- Includes multi-column & single-column indexes for collection_id, status, 
-- scheme_name, department, effective_date, and file_hash.
-- =============================================================================

-- 1. Roles Table
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255),
    permissions TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_roles_name ON roles(name);

-- 2. Departments Table (Supporting Domain Entity)
CREATE TABLE IF NOT EXISTS departments (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_departments_code ON departments(code);

-- 3. Users Table (Entity 1)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role_id VARCHAR(36) REFERENCES roles(id) ON DELETE SET NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'CITIZEN',
    department VARCHAR(255),
    department_id VARCHAR(36) REFERENCES departments(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_role ON users(role);

-- 4. Document Collections Table (Entity 3)
CREATE TABLE IF NOT EXISTS document_collections (
    id VARCHAR(36) PRIMARY KEY,
    department_id VARCHAR(36) REFERENCES departments(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_collections_slug ON document_collections(slug);
CREATE INDEX IF NOT EXISTS ix_document_collections_department_id ON document_collections(department_id);

-- 5. Documents Table (Entity 4)
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY,
    collection_id VARCHAR(36) NOT NULL REFERENCES document_collections(id) ON DELETE CASCADE,
    scheme_name VARCHAR(255) NOT NULL,
    department VARCHAR(255) NOT NULL,
    state_or_district VARCHAR(150) DEFAULT 'National / All States',
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    publication_date TIMESTAMP,
    effective_date TIMESTAMP,
    original_filename VARCHAR(255) NOT NULL,
    storage_file_key VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    file_hash VARCHAR(64) NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Required Indexes on Documents Table
CREATE INDEX IF NOT EXISTS ix_documents_collection_id ON documents(collection_id);
CREATE INDEX IF NOT EXISTS ix_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS ix_documents_scheme_name ON documents(scheme_name);
CREATE INDEX IF NOT EXISTS ix_documents_department ON documents(department);
CREATE INDEX IF NOT EXISTS ix_documents_effective_date ON documents(effective_date);
CREATE INDEX IF NOT EXISTS ix_documents_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS ix_documents_collection_status ON documents(collection_id, status);

-- 6. Document Versions Table (Entity 5)
CREATE TABLE IF NOT EXISTS document_versions (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    original_filename VARCHAR(255) NOT NULL,
    storage_file_key VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    file_hash VARCHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    total_pages INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'PROCESSING',
    effective_date TIMESTAMP,
    change_summary TEXT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_versions_document_id ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS ix_document_versions_status ON document_versions(status);
CREATE INDEX IF NOT EXISTS ix_document_versions_file_hash ON document_versions(file_hash);

-- 7. Document Pages Table (Entity 6)
CREATE TABLE IF NOT EXISTS document_pages (
    id VARCHAR(36) PRIMARY KEY,
    version_id VARCHAR(36) NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    document_id VARCHAR(36) REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    native_text TEXT,
    ocr_text TEXT,
    extraction_method VARCHAR(20) NOT NULL DEFAULT 'NATIVE',
    ocr_confidence REAL,
    is_scanned BOOLEAN NOT NULL DEFAULT 0,
    requires_admin_review BOOLEAN NOT NULL DEFAULT 0,
    review_reason VARCHAR(255),
    storage_image_path VARCHAR(500),
    word_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_pages_version_id ON document_pages(version_id);
CREATE INDEX IF NOT EXISTS ix_document_pages_document_id ON document_pages(document_id);
CREATE INDEX IF NOT EXISTS ix_document_pages_page_num ON document_pages(version_id, page_number);

-- 8. Extracted Text Chunks Table (Entity 7)
CREATE TABLE IF NOT EXISTS extracted_chunks (
    id VARCHAR(36) PRIMARY KEY,
    page_id VARCHAR(36) NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,
    version_id VARCHAR(36) NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL DEFAULT 1,
    page_range VARCHAR(50) DEFAULT '1',
    section_heading VARCHAR(255),
    chunk_text TEXT NOT NULL,
    normalized_text TEXT,
    token_count INTEGER NOT NULL DEFAULT 0,
    start_char_offset INTEGER NOT NULL DEFAULT 0,
    end_char_offset INTEGER NOT NULL DEFAULT 0,
    metadata_json JSON,
    vector_id VARCHAR(100),
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    embedding_dimension INTEGER DEFAULT 1536,
    indexed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_extracted_chunks_page_id ON extracted_chunks(page_id);
CREATE INDEX IF NOT EXISTS ix_extracted_chunks_version_id ON extracted_chunks(version_id);
CREATE INDEX IF NOT EXISTS ix_extracted_chunks_document_id ON extracted_chunks(document_id);
CREATE INDEX IF NOT EXISTS ix_extracted_chunks_page_number ON extracted_chunks(page_number);
CREATE INDEX IF NOT EXISTS ix_extracted_chunks_vector_id ON extracted_chunks(vector_id);

-- 9. Processing Jobs Table (Entity 8)
CREATE TABLE IF NOT EXISTS processing_jobs (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_id VARCHAR(36) REFERENCES document_versions(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    progress_percent INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    summary_details JSON,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_document_id ON processing_jobs(document_id);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_status ON processing_jobs(status);


-- 10. Document Metadata Table (Entity 9)
CREATE TABLE IF NOT EXISTS document_metadata (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_id VARCHAR(36) REFERENCES document_versions(id) ON DELETE CASCADE,
    meta_key VARCHAR(100) NOT NULL,
    meta_value TEXT NOT NULL,
    data_type VARCHAR(20) NOT NULL DEFAULT 'string',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_metadata_document_id ON document_metadata(document_id);
CREATE INDEX IF NOT EXISTS ix_document_metadata_meta_key ON document_metadata(meta_key);

-- 11. Search Sessions Table (Entity 10)
CREATE TABLE IF NOT EXISTS search_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    collection_id VARCHAR(36) REFERENCES document_collections(id) ON DELETE SET NULL,
    session_token VARCHAR(100) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_search_sessions_user_id ON search_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_search_sessions_token ON search_sessions(session_token);

-- 12. Questions and Answers Table (Entity 11)
CREATE TABLE IF NOT EXISTS question_answers (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) REFERENCES search_sessions(id) ON DELETE SET NULL,
    collection_id VARCHAR(36) REFERENCES document_collections(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    is_refusal BOOLEAN NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_question_answers_session_id ON question_answers(session_id);
CREATE INDEX IF NOT EXISTS ix_question_answers_collection_id ON question_answers(collection_id);

-- 13. Citations Table (Entity 12)
CREATE TABLE IF NOT EXISTS citations (
    id VARCHAR(36) PRIMARY KEY,
    qa_id VARCHAR(36) NOT NULL REFERENCES question_answers(id) ON DELETE CASCADE,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id VARCHAR(36) REFERENCES extracted_chunks(id) ON DELETE SET NULL,
    page_number INTEGER NOT NULL,
    document_title VARCHAR(255) NOT NULL,
    excerpt TEXT NOT NULL,
    confidence_score FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_citations_qa_id ON citations(qa_id);
CREATE INDEX IF NOT EXISTS ix_citations_document_id ON citations(document_id);

-- 14. Audit Events Table (Entity 13)
CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    entity_table VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100),
    metadata_json TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_audit_events_user_id ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_action_type ON audit_events(action_type);
CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events(created_at);

-- 15. User Feedback Table (Entity 14)
CREATE TABLE IF NOT EXISTS user_feedback (
    id VARCHAR(36) PRIMARY KEY,
    qa_id VARCHAR(36) NOT NULL REFERENCES question_answers(id) ON DELETE CASCADE,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL,
    feedback_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_user_feedback_qa_id ON user_feedback(qa_id);
CREATE INDEX IF NOT EXISTS ix_user_feedback_user_id ON user_feedback(user_id);

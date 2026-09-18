"""
SQLAlchemy ORM models representing the complete 14-entity schema for WelfareConnect.
Includes indexes for collection_id, status, scheme_name, department, effective_date, and file_hash.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


# -----------------------------------------------------------------------------
# Document Status Enum
# -----------------------------------------------------------------------------
class DocumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"
    DELETED = "DELETED"


# -----------------------------------------------------------------------------
# 1. Roles & Permissions (Entity 2)
# -----------------------------------------------------------------------------
class Role(Base):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    permissions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="role_rel")


# -----------------------------------------------------------------------------
# Department Entity (Supporting Domain Entity)
# -----------------------------------------------------------------------------
class Department(Base):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    collections = relationship("DocumentCollection", back_populates="department_rel")
    users = relationship("User", back_populates="department_rel")


# -----------------------------------------------------------------------------
# 2. Users (Entity 1)
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=True)
    role = Column(String(50), default="CITIZEN", nullable=False)  # SYSTEM_ADMIN, SCHEME_ADMIN, HELPDESK, CITIZEN
    department = Column(String(255), nullable=True)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    role_rel = relationship("Role", back_populates="users")
    department_rel = relationship("Department", back_populates="users")
    audit_events = relationship("AuditEvent", back_populates="user")
    search_sessions = relationship("SearchSession", back_populates="user")
    feedbacks = relationship("UserFeedback", back_populates="user")


# -----------------------------------------------------------------------------
# 3. Document Collections (Entity 3)
# -----------------------------------------------------------------------------
class DocumentCollection(Base):
    __tablename__ = "document_collections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    department_rel = relationship("Department", back_populates="collections")
    documents = relationship("Document", back_populates="collection", cascade="all, delete-orphan")
    search_sessions = relationship("SearchSession", back_populates="collection")


# -----------------------------------------------------------------------------
# 4. Documents (Entity 4)
# -----------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    collection_id = Column(String(36), ForeignKey("document_collections.id"), nullable=False, index=True)
    
    # Metadata fields
    scheme_name = Column(String(255), nullable=False, index=True)
    department = Column(String(255), nullable=False, index=True)
    state_or_district = Column(String(150), nullable=True, default="National / All States")
    language = Column(String(10), default="en", nullable=False)
    publication_date = Column(DateTime, nullable=True)
    effective_date = Column(DateTime, nullable=True, index=True)
    
    # File Storage & Integrity fields
    original_filename = Column(String(255), nullable=False)
    storage_file_key = Column(String(500), nullable=False)
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    version_number = Column(Integer, default=1, nullable=False)
    
    # Lifecycle Status: ACTIVE, ARCHIVED, PROCESSING, FAILED, DELETED
    status = Column(String(20), default=DocumentStatus.ACTIVE.value, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Legacy alias properties for backward compatibility
    @property
    def title(self) -> str:
        return self.scheme_name

    @property
    def department_name(self) -> str:
        return self.department

    collection = relationship("DocumentCollection", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    metadata_entries = relationship("DocumentMetadata", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="document")


# Explicit Multi-Column Indexes for Documents Table
Index("ix_documents_collection_status", Document.collection_id, Document.status)
Index("ix_documents_dept_effective", Document.department, Document.effective_date)
Index("ix_documents_scheme_status", Document.scheme_name, Document.status)


# -----------------------------------------------------------------------------
# 5. Document Versions (Entity 5)
# -----------------------------------------------------------------------------
class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_file_key = Column(String(500), nullable=False)
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    total_pages = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default=DocumentStatus.PROCESSING.value, nullable=False, index=True)
    effective_date = Column(DateTime, nullable=True)
    change_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Backward compatibility alias
    @property
    def storage_pdf_path(self) -> str:
        return self.storage_file_key

    @property
    def file_hash_sha256(self) -> str:
        return self.file_hash

    document = relationship("Document", back_populates="versions")
    pages = relationship("DocumentPage", back_populates="version", cascade="all, delete-orphan")
    chunks = relationship("ExtractedChunk", back_populates="version", cascade="all, delete-orphan")
    metadata_entries = relationship("DocumentMetadata", back_populates="version", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="version", cascade="all, delete-orphan")


# -----------------------------------------------------------------------------
# 6. Document Pages (Entity 6)
# -----------------------------------------------------------------------------
class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True, index=True)
    page_number = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    storage_image_path = Column(String(500), nullable=True)
    word_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    version = relationship("DocumentVersion", back_populates="pages")
    chunks = relationship("ExtractedChunk", back_populates="page", cascade="all, delete-orphan")


# -----------------------------------------------------------------------------
# 7. Extracted Text Chunks (Entity 7)
# -----------------------------------------------------------------------------
class ExtractedChunk(Base):
    __tablename__ = "extracted_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    page_id = Column(String(36), ForeignKey("document_pages.id"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    start_char_offset = Column(Integer, default=0, nullable=False)
    end_char_offset = Column(Integer, default=0, nullable=False)
    vector_id = Column(String(100), nullable=True, index=True)  # Pinecone Vector ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    page = relationship("DocumentPage", back_populates="chunks")
    version = relationship("DocumentVersion", back_populates="chunks")
    citations = relationship("Citation", back_populates="chunk")


# Alias DocumentChunk to ExtractedChunk for backwards compatibility
DocumentChunk = ExtractedChunk


# -----------------------------------------------------------------------------
# 8. Processing Jobs (Entity 8)
# -----------------------------------------------------------------------------
class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=True, index=True)
    job_type = Column(String(50), nullable=False)  # PDF_INGESTION, OCR_EXTRACT, EMBEDDING_GEN, REINDEX
    status = Column(String(30), default="QUEUED", nullable=False, index=True)  # QUEUED, RUNNING, COMPLETED, FAILED
    progress_percent = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="processing_jobs")
    version = relationship("DocumentVersion", back_populates="processing_jobs")


# -----------------------------------------------------------------------------
# 9. Document Metadata (Entity 9)
# -----------------------------------------------------------------------------
class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("document_versions.id"), nullable=True, index=True)
    meta_key = Column(String(100), nullable=False, index=True)
    meta_value = Column(Text, nullable=False)
    data_type = Column(String(20), default="string", nullable=False)  # string, json, integer, date, boolean
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="metadata_entries")
    version = relationship("DocumentVersion", back_populates="metadata_entries")


# -----------------------------------------------------------------------------
# 10. Search Sessions (Entity 10)
# -----------------------------------------------------------------------------
class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    collection_id = Column(String(36), ForeignKey("document_collections.id"), nullable=True, index=True)
    session_token = Column(String(100), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="search_sessions")
    collection = relationship("DocumentCollection", back_populates="search_sessions")
    questions_and_answers = relationship("QuestionAnswer", back_populates="session", cascade="all, delete-orphan")


# -----------------------------------------------------------------------------
# 11. Questions and Answers (Entity 11)
# -----------------------------------------------------------------------------
class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("search_sessions.id"), nullable=True, index=True)
    collection_id = Column(String(36), ForeignKey("document_collections.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    is_refusal = Column(Boolean, default=False, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("SearchSession", back_populates="questions_and_answers")
    citations = relationship("Citation", back_populates="qa_record", cascade="all, delete-orphan")
    feedbacks = relationship("UserFeedback", back_populates="qa_record", cascade="all, delete-orphan")


# Backward compatibility alias
QueryLog = QuestionAnswer


# -----------------------------------------------------------------------------
# 12. Citations (Entity 12)
# -----------------------------------------------------------------------------
class Citation(Base):
    __tablename__ = "citations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    qa_id = Column(String(36), ForeignKey("question_answers.id"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    chunk_id = Column(String(36), ForeignKey("extracted_chunks.id"), nullable=True, index=True)
    page_number = Column(Integer, nullable=False)
    document_title = Column(String(255), nullable=False)
    excerpt = Column(Text, nullable=False)
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    qa_record = relationship("QuestionAnswer", back_populates="citations")
    document = relationship("Document", back_populates="citations")
    chunk = relationship("ExtractedChunk", back_populates="citations")


# -----------------------------------------------------------------------------
# 13. Audit Events (Entity 13)
# -----------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action_type = Column(String(100), nullable=False, index=True)  # USER_LOGIN, DOC_UPLOAD, DOC_DEPRECATE, etc.
    entity_table = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Legacy aliases
    @property
    def action(self) -> str:
        return self.action_type

    @property
    def details(self) -> dict:
        return self.metadata_json or {}

    user = relationship("User", back_populates="audit_events")


# Backward compatibility alias
AuditLog = AuditEvent


# -----------------------------------------------------------------------------
# 14. User Feedback (Entity 14)
# -----------------------------------------------------------------------------
class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    qa_id = Column(String(36), ForeignKey("question_answers.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    rating = Column(Integer, nullable=False)  # 1 for thumbs up, -1 for thumbs down
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    qa_record = relationship("QuestionAnswer", back_populates="feedbacks")
    user = relationship("User", back_populates="feedbacks")

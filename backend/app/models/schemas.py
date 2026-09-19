"""
Pydantic schemas for request and response validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# User Roles & Auth Schemas
# ---------------------------------------------------------

class UserRole(str, Enum):
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    SCHEME_ADMIN = "SCHEME_ADMIN"
    HELPDESK = "HELPDESK"
    CITIZEN = "CITIZEN"


ROLE_PERMISSIONS: Dict[UserRole, List[str]] = {
    UserRole.SYSTEM_ADMIN: [
        "admin:all",
        "users:manage",
        "audit:read",
        "docs:all",
        "docs:upload",
        "docs:process",
        "docs:archive",
        "docs:delete",
        "collections:manage",
        "query:execute",
        "citations:preview",
        "feedback:submit",
        "history:read",
        "eligibility:check",
    ],
    UserRole.SCHEME_ADMIN: [
        "docs:upload",
        "docs:process",
        "docs:archive",
        "docs:delete",
        "docs:all",
        "collections:manage",
        "audit:read",
        "query:execute",
        "citations:preview",
        "feedback:submit",
    ],
    UserRole.HELPDESK: [
        "query:execute",
        "citations:preview",
        "feedback:submit",
        "history:read",
        "eligibility:check",
    ],
    UserRole.CITIZEN: [
        "query:execute",
        "citations:preview",
        "feedback:submit",
    ],
}


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterCitizenRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2)


class CreateStaffRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2)
    role: UserRole
    department: Optional[str] = "General Administration"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    department: Optional[str] = None
    permissions: List[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuthTokenPayload(BaseModel):
    user_id: str
    email: str
    role: UserRole
    permissions: List[str] = []


class AuthSessionResponse(BaseModel):
    user: UserOut
    token: str
    token_type: str = "bearer"
    expires_in_minutes: int


# ---------------------------------------------------------
# Document & Collection Schemas
# ---------------------------------------------------------

class CollectionBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    department: Optional[str] = None


class CollectionCreate(CollectionBase):
    pass


class CollectionOut(CollectionBase):
    id: str
    is_active: bool = True
    total_documents: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentVersionStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DEPRECATED = "DEPRECATED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class DocumentUploadRequest(BaseModel):
    collection_id: str
    scheme_name: str
    department: str
    state_or_district: Optional[str] = "National / All States"
    language: Optional[str] = "en"
    original_filename: str
    storage_file_key: Optional[str] = None
    file_content_base64: Optional[str] = None
    publication_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    version_number: Optional[int] = 1
    visibility: Optional[str] = "public"
    is_official_source_confirmed: Optional[bool] = True


class DocumentOut(BaseModel):
    id: str
    collection_id: str
    title: str
    scheme_code: Optional[str] = None
    department: Optional[str] = None
    state_or_district: Optional[str] = None
    language: Optional[str] = "en"
    publication_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    current_version: int = 1
    status: DocumentVersionStatus = DocumentVersionStatus.ACTIVE
    total_pages: int = 0
    file_hash: Optional[str] = None
    file_size_bytes: Optional[int] = 0
    visibility: Optional[str] = "public"
    duplicate_warning: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



class DocumentVersionOut(BaseModel):
    id: str
    document_id: str
    version_number: int
    original_filename: str
    status: str
    effective_date: Optional[datetime] = None
    change_summary: Optional[str] = None
    file_size_bytes: int = 0
    total_pages: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentVersionCreate(BaseModel):
    version_number: int
    original_filename: str
    storage_file_key: Optional[str] = None
    file_size_bytes: Optional[int] = 0
    effective_date: Optional[datetime] = None
    change_summary: Optional[str] = None


class DocumentConflictWarning(BaseModel):
    scheme_name: str
    collection_id: str
    conflicting_document_ids: List[str]
    conflicting_version_numbers: List[int]
    message: str


class DocumentActionResponse(BaseModel):
    success: bool
    document_id: str
    action: str
    status: str
    message: str


class ProcessingSummaryOut(BaseModel):
    job_id: str
    document_id: str
    version_id: Optional[str] = None
    status: str
    progress_percent: int
    total_pages: int
    native_text_pages: int
    ocr_pages: int
    failed_pages: int
    low_confidence_pages: int
    scanned_pages: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PageOut(BaseModel):
    page_number: int
    text_preview: str
    image_url: Optional[str] = None
    native_text: Optional[str] = None
    ocr_text: Optional[str] = None
    extraction_method: Optional[str] = "NATIVE"
    ocr_confidence: Optional[float] = None
    is_scanned: Optional[bool] = False
    requires_admin_review: Optional[bool] = False
    review_reason: Optional[str] = None
    word_count: Optional[int] = 0



# ---------------------------------------------------------
# Query, Eligibility & Feedback Schemas
# ---------------------------------------------------------

class CitationOut(BaseModel):
    document_id: str
    document_title: str
    page_number: int
    excerpt: str
    score: float
    version_number: Optional[int] = 1
    status: Optional[str] = "ACTIVE"
    is_historical: Optional[bool] = False


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    collection_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    include_historical: Optional[bool] = False
    include_archived: Optional[bool] = False



class QueryResponse(BaseModel):
    qa_id: Optional[str] = None
    answer: str
    citations: List[CitationOut] = []
    is_refusal: bool = False
    disclaimer: str = (
        "Informational purpose only. Does not constitute official legal eligibility "
        "determination. Refer to the cited official document for authoritative guidance."
    )
    latency_ms: int = 0


class EligibilityCheckRequest(BaseModel):
    collection_id: Optional[str] = None
    applicant_age: Optional[int] = None
    annual_income: Optional[float] = None
    landholding_hectares: Optional[float] = None
    residence_state: Optional[str] = None
    occupational_category: Optional[str] = None


class EligibilityCheckResponse(BaseModel):
    eligible_schemes: List[Dict[str, Any]]
    ineligible_schemes: List[Dict[str, Any]]
    evaluation_summary: str
    citations: List[CitationOut]
    disclaimer: str = (
        "Preliminary algorithmic evaluation based on indexed policy circulars. "
        "Official eligibility must be verified by the competent department."
    )


class QueryHistoryItem(BaseModel):
    id: str
    session_id: Optional[str]
    question: str
    answer: str
    is_refusal: bool
    latency_ms: int
    created_at: datetime


class FeedbackCreateRequest(BaseModel):
    qa_id: str
    rating: int = Field(..., description="1 for helpful, -1 for unhelpful")
    feedback_text: Optional[str] = None


class FeedbackResponse(BaseModel):
    success: bool
    feedback_id: str
    message: str


# ---------------------------------------------------------
# Health Check Schemas
# ---------------------------------------------------------

class HealthComponentStatus(BaseModel):
    status: str
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    components: Dict[str, HealthComponentStatus]
    timestamp: datetime

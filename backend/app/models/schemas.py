"""
Pydantic schemas for request and response validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# User Roles & Auth Schemas (Prompt 05 Preservation)
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
        "collections:manage",
    ],
    UserRole.SCHEME_ADMIN: [
        "docs:upload",
        "docs:process",
        "docs:archive",
        "docs:delete",
        "collections:manage",
        "audit:read",
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
    DEPRECATED = "DEPRECATED"
    FAILED = "FAILED"


class DocumentOut(BaseModel):
    id: str
    collection_id: str
    title: str
    scheme_code: Optional[str] = None
    department: Optional[str] = None
    current_version: int = 1
    status: DocumentVersionStatus = DocumentVersionStatus.ACTIVE
    total_pages: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    page_number: int
    text_preview: str
    image_url: Optional[str] = None


# ---------------------------------------------------------
# Query & Search Schemas
# ---------------------------------------------------------

class CitationOut(BaseModel):
    document_id: str
    document_title: str
    page_number: int
    excerpt: str
    score: float


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    collection_id: Optional[str] = None
    document_ids: Optional[List[str]] = None


class QueryResponse(BaseModel):
    answer: str
    citations: List[CitationOut] = []
    is_refusal: bool = False
    disclaimer: str = (
        "Informational purpose only. Does not constitute official legal eligibility "
        "determination. Refer to the cited official document for authoritative guidance."
    )
    latency_ms: int = 0


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

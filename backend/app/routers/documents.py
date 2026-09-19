from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session
from backend.app.core.dependencies import get_optional_user, require_permissions
from backend.app.db.session import get_db
from backend.app.models.schemas import (
    DocumentActionResponse,
    DocumentConflictWarning,
    DocumentOut,
    DocumentUploadRequest,
    DocumentVersionCreate,
    DocumentVersionOut,
    PageOut,
    ProcessingSummaryOut,
    UserOut,
)
from backend.app.services.document_service import DocumentService


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=List[DocumentOut])
def list_documents(
    collection_id: Optional[str] = Query(None, description="Filter documents by collection ID"),
    include_archived: bool = Query(False, description="Include archived documents for administrators"),
    current_user: Optional[UserOut] = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> List[DocumentOut]:
    """
    List documents.
    Public and Citizens only see ACTIVE documents.
    Administrators with 'docs:all' or 'docs:upload' can view archived documents if requested.
    """
    can_view_archived = False
    if current_user and ("docs:all" in current_user.permissions or "admin:all" in current_user.permissions):
        can_view_archived = include_archived

    return DocumentService.list_documents(db, collection_id, include_archived=can_view_archived)


@router.post("/upload", response_model=DocumentOut)
def upload_document(
    data: DocumentUploadRequest,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["docs:upload"])),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Upload and register a new official scheme PDF via JSON (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.upload_document(
        db=db,
        data=data,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


@router.post("/upload-file", response_model=DocumentOut)
async def upload_document_file(
    req: Request,
    file: UploadFile = File(...),
    collection_id: str = Form(...),
    scheme_name: str = Form(...),
    department: str = Form(...),
    state_or_district: Optional[str] = Form("National / All States"),
    language: Optional[str] = Form("en"),
    publication_date: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    version_number: Optional[int] = Form(1),
    visibility: Optional[str] = Form("public"),
    is_official_source_confirmed: bool = Form(True),
    current_user: UserOut = Depends(require_permissions(["docs:upload"])),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Upload binary PDF file with server-side validation, duplicate detection, and hash generation (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    file_bytes = await file.read()

    pub_date: Optional[datetime] = None
    eff_date: Optional[datetime] = None
    if publication_date:
        try:
            pub_date = datetime.fromisoformat(publication_date.replace("Z", "+00:00"))
        except Exception:
            pass
    if effective_date:
        try:
            eff_date = datetime.fromisoformat(effective_date.replace("Z", "+00:00"))
        except Exception:
            pass

    return DocumentService.upload_document_file(
        db=db,
        file_content=file_bytes,
        filename=file.filename or "official_scheme.pdf",
        collection_id=collection_id,
        scheme_name=scheme_name,
        department=department,
        admin_user_id=current_user.id,
        state_or_district=state_or_district,
        language=language,
        publication_date=pub_date,
        effective_date=eff_date,
        version_number=version_number,
        visibility=visibility,
        is_official_source_confirmed=is_official_source_confirmed,
        ip_address=client_ip,
    )


@router.post("/{document_id}/process", response_model=DocumentActionResponse)
def process_document(
    document_id: str,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["docs:process"])),
    db: Session = Depends(get_db),
) -> DocumentActionResponse:
    """Trigger background re-indexing and chunk extraction (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.process_document(
        db=db,
        document_id=document_id,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


@router.put("/{document_id}/archive", response_model=DocumentActionResponse)
def archive_document(
    document_id: str,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["docs:archive"])),
    db: Session = Depends(get_db),
) -> DocumentActionResponse:
    """Archive a document and all its versions (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.archive_document(
        db=db,
        document_id=document_id,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


@router.put("/{document_id}/restore", response_model=DocumentActionResponse)
def restore_document(
    document_id: str,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["docs:archive"])),
    db: Session = Depends(get_db),
) -> DocumentActionResponse:
    """Restore an archived document back to active status (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.restore_document(
        db=db,
        document_id=document_id,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


@router.get("/{document_id}/versions", response_model=List[DocumentVersionOut])
def get_document_versions(
    document_id: str,
    current_user: Optional[UserOut] = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> List[DocumentVersionOut]:
    """Retrieve full version history for a given scheme document."""
    return DocumentService.list_document_versions(db, document_id)


@router.post("/{document_id}/versions", response_model=DocumentVersionOut)
def create_document_version(
    document_id: str,
    data: DocumentVersionCreate,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["docs:upload"])),
    db: Session = Depends(get_db),
) -> DocumentVersionOut:
    """Register a new release version for an existing scheme document (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.create_document_version(
        db=db,
        document_id=document_id,
        version_number=data.version_number,
        original_filename=data.original_filename,
        admin_user_id=current_user.id,
        storage_file_key=data.storage_file_key,
        file_size_bytes=data.file_size_bytes or (1024 * 1024),
        effective_date=data.effective_date,
        change_summary=data.change_summary,
        ip_address=client_ip,
    )


@router.get("/conflicts", response_model=List[DocumentConflictWarning])
def get_version_conflicts(
    collection_id: Optional[str] = Query(None, description="Filter conflict detection by collection ID"),
    current_user: UserOut = Depends(require_permissions(["docs:all"])),
    db: Session = Depends(get_db),
) -> List[DocumentConflictWarning]:
    """Detect overlapping active versions/documents covering the same scheme (Administrator only)."""
    return DocumentService.detect_version_conflicts(db, collection_id)


@router.delete("/{document_id}", response_model=DocumentActionResponse)
def delete_document(
    document_id: str,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["docs:delete"])),
    db: Session = Depends(get_db),
) -> DocumentActionResponse:
    """Soft-delete an official scheme document (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.delete_document(
        db=db,
        document_id=document_id,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


@router.get("/{document_id}/pages/{page_number}", response_model=PageOut)
def get_page_preview(
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
) -> PageOut:
    """Retrieve rendered page preview and text for citation verification."""
    return DocumentService.get_page_preview(db, document_id, page_number)


@router.get("/{document_id}/processing-summary", response_model=ProcessingSummaryOut)
def get_processing_summary(
    document_id: str,
    current_user: Optional[UserOut] = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ProcessingSummaryOut:
    """Retrieve document ingestion summary: native text pages, OCR pages, low-confidence review pages, failed pages."""
    return DocumentService.get_processing_summary(db, document_id)



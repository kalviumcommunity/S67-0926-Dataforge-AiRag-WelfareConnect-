"""
Document and Page Management Endpoints.
Enforces role and permission checks for upload, processing, archiving, and deletion.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.app.core.dependencies import get_optional_user, require_permissions
from backend.app.db.session import get_db
from backend.app.models.schemas import (
    DocumentActionResponse,
    DocumentOut,
    DocumentUploadRequest,
    PageOut,
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
    """Upload and register a new official scheme PDF (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.upload_document(
        db=db,
        data=data,
        admin_user_id=current_user.id,
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
    """Archive a document and exclude it from public search (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.archive_document(
        db=db,
        document_id=document_id,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


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

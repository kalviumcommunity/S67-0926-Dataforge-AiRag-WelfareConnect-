"""
Document and Page Management Endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.schemas import DocumentOut, PageOut
from backend.app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=List[DocumentOut])
def list_documents(
    collection_id: Optional[str] = Query(None, description="Filter documents by collection ID"),
    db: Session = Depends(get_db),
) -> List[DocumentOut]:
    """List documents optionally filtered by collection ID."""
    return DocumentService.list_documents(db, collection_id)


@router.get("/{document_id}/pages/{page_number}", response_model=PageOut)
def get_page_preview(
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
) -> PageOut:
    """Retrieve rendered page preview and text for citation verification."""
    return DocumentService.get_page_preview(db, document_id, page_number)

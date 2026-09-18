"""
Document Collection Endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.dependencies import require_roles
from backend.app.db.session import get_db
from backend.app.models.schemas import CollectionCreate, CollectionOut, UserOut, UserRole
from backend.app.services.document_service import DocumentService

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=List[CollectionOut])
def list_collections(db: Session = Depends(get_db)) -> List[CollectionOut]:
    """List all active public scheme document collections."""
    return DocumentService.list_collections(db)


@router.post("", response_model=CollectionOut)
def create_collection(
    data: CollectionCreate,
    current_user: UserOut = Depends(require_roles([UserRole.SYSTEM_ADMIN, UserRole.SCHEME_ADMIN])),
    db: Session = Depends(get_db),
) -> CollectionOut:
    """Create a new document collection (Admin only)."""
    return DocumentService.create_collection(db, data, current_user.id)

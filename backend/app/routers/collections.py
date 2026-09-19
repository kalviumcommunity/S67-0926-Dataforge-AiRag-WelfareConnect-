"""
Document Collection Endpoints.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.app.core.dependencies import require_permissions, require_roles
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
    req: Request,
    current_user: UserOut = Depends(require_permissions(["collections:manage"])),
    db: Session = Depends(get_db),
) -> CollectionOut:
    """Create a new document collection (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.create_collection(
        db=db,
        data=data,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )


@router.delete("/{collection_id}", response_model=Dict[str, Any])
def delete_collection(
    collection_id: str,
    req: Request,
    current_user: UserOut = Depends(require_permissions(["collections:manage"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Deactivate a document collection (Administrator only)."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    return DocumentService.delete_collection(
        db=db,
        collection_id=collection_id,
        admin_user_id=current_user.id,
        ip_address=client_ip,
    )

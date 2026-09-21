"""
Indexing Management, Rebuild, and Vector Administration Router.
Enforces administrative permissions ('admin:all', 'docs:all') for vector index maintenance.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import require_permissions
from backend.app.db.session import get_db
from backend.app.models.schemas import UserOut
from backend.app.services.indexing_service import indexing_service
from backend.app.services.pinecone_service import pinecone_service

router = APIRouter(prefix="/indexing", tags=["Indexing & Vectors"])


@router.get("/stats")
def get_indexing_stats(
    current_user: UserOut = Depends(require_permissions(["admin:all", "docs:all"])),
) -> Dict[str, Any]:
    """Get status and configuration of Pinecone vector index and embeddings."""
    return pinecone_service.health_check()


@router.post("/reindex-version/{version_id}")
def reindex_document_version(
    version_id: str,
    current_user: UserOut = Depends(require_permissions(["admin:all", "docs:all"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Administrator endpoint to re-index all chunk vectors for a single document version.
    """
    try:
        return indexing_service.upsert_document_version_vectors(db=db, version_id=version_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/reindex-collection/{collection_id}")
def reindex_collection(
    collection_id: str,
    current_user: UserOut = Depends(require_permissions(["admin:all", "docs:all"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Administrator endpoint to re-index all active documents in a collection after metadata changes.
    """
    try:
        return indexing_service.reindex_collection(db=db, collection_id=collection_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/rebuild")
def rebuild_all_indexes(
    current_user: UserOut = Depends(require_permissions(["admin:all"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Administrator command to trigger a complete re-index of all active collections.
    """
    try:
        return indexing_service.rebuild_all_indexes(db=db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/version/{version_id}")
def delete_version_vectors(
    version_id: str,
    current_user: UserOut = Depends(require_permissions(["admin:all", "docs:all"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Administrator endpoint to purge all vector embeddings for a specific document version.
    """
    try:
        return indexing_service.delete_document_version_vectors(db=db, version_id=version_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

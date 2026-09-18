"""
Document and Collection management service.
Handles metadata updates, version transitions, and file catalog indexing.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.models.db_models import (
    Document,
    DocumentCollection,
    DocumentPage,
    DocumentVersion,
)
from backend.app.models.schemas import (
    CollectionCreate,
    CollectionOut,
    DocumentOut,
    DocumentVersionStatus,
    PageOut,
)
from backend.app.services.audit_service import AuditService


class DocumentService:
    @staticmethod
    def list_collections(db: Session) -> List[CollectionOut]:
        """List all active scheme collections."""
        collections = db.query(DocumentCollection).filter(DocumentCollection.is_active.is_(True)).all()
        results = []
        for c in collections:
            doc_count = db.query(Document).filter(Document.collection_id == c.id).count()
            dept_name = c.department.name if c.department else None
            results.append(
                CollectionOut(
                    id=c.id,
                    name=c.name,
                    slug=c.slug,
                    description=c.description,
                    department=dept_name,
                    is_active=c.is_active,
                    total_documents=doc_count,
                    created_at=c.created_at,
                )
            )
        return results

    @staticmethod
    def create_collection(
        db: Session,
        data: CollectionCreate,
        admin_user_id: str
    ) -> CollectionOut:
        """Create a new scheme collection."""
        existing = db.query(DocumentCollection).filter(DocumentCollection.slug == data.slug).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Collection with slug '{data.slug}' already exists."
            )

        col = DocumentCollection(
            name=data.name,
            slug=data.slug,
            description=data.description,
            is_active=True,
        )
        db.add(col)
        db.commit()
        db.refresh(col)

        AuditService.log_event(
            db=db,
            action="COLLECTION_CREATED",
            entity_type="document_collections",
            user_id=admin_user_id,
            entity_id=col.id,
            details={"name": col.name, "slug": col.slug},
        )

        return CollectionOut(
            id=col.id,
            name=col.name,
            slug=col.slug,
            description=col.description,
            department=None,
            is_active=col.is_active,
            total_documents=0,
            created_at=col.created_at,
        )

    @staticmethod
    def list_documents(
        db: Session,
        collection_id: Optional[str] = None
    ) -> List[DocumentOut]:
        """List documents optionally filtered by collection."""
        query = db.query(Document)
        if collection_id:
            query = query.filter(Document.collection_id == collection_id)
        docs = query.all()

        results = []
        for d in docs:
            latest_version = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == d.id)
                .order_by(DocumentVersion.version_number.desc())
                .first()
            )
            v_num = latest_version.version_number if latest_version else 1
            v_status = DocumentVersionStatus(latest_version.status) if latest_version else DocumentVersionStatus.ACTIVE
            total_pages = latest_version.total_pages if latest_version else 0

            results.append(
                DocumentOut(
                    id=d.id,
                    collection_id=d.collection_id,
                    title=d.title,
                    scheme_code=d.scheme_code,
                    department=d.department_name,
                    current_version=v_num,
                    status=v_status,
                    total_pages=total_pages,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
            )
        return results

    @staticmethod
    def get_page_preview(
        db: Session,
        document_id: str,
        page_number: int
    ) -> PageOut:
        """Fetch page text and image preview for citation inspection."""
        page = (
            db.query(DocumentPage)
            .join(DocumentVersion, DocumentPage.version_id == DocumentVersion.id)
            .filter(
                DocumentVersion.document_id == document_id,
                DocumentPage.page_number == page_number
            )
            .first()
        )
        if not page:
            # Fallback preview if document pages are being processed
            return PageOut(
                page_number=page_number,
                text_preview=f"Official scheme circular excerpt from page {page_number}.",
                image_url=None,
            )

        return PageOut(
            page_number=page.page_number,
            text_preview=page.raw_text[:1000],
            image_url=page.storage_image_path,
        )

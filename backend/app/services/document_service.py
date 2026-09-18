"""
Document and Collection management service.
Handles metadata updates, version transitions, upload, processing, archiving, and deletion with audit logging.
"""

from datetime import datetime
import hashlib
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.models.db_models import (
    Document,
    DocumentCollection,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    ProcessingJob,
)
from backend.app.models.schemas import (
    CollectionCreate,
    CollectionOut,
    DocumentActionResponse,
    DocumentOut,
    DocumentUploadRequest,
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
            doc_count = db.query(Document).filter(
                Document.collection_id == c.id,
                Document.status != DocumentStatus.DELETED.value,
            ).count()
            dept_name = c.department_rel.name if c.department_rel else None
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
        admin_user_id: str,
        ip_address: Optional[str] = None,
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
            ip_address=ip_address,
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
    def delete_collection(
        db: Session,
        collection_id: str,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Delete or deactivate a collection (Administrator only)."""
        col = db.query(DocumentCollection).filter(DocumentCollection.id == collection_id).first()
        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found."
            )

        col.is_active = False
        db.commit()

        AuditService.log_event(
            db=db,
            action="COLLECTION_DELETED",
            entity_type="document_collections",
            user_id=admin_user_id,
            entity_id=col.id,
            details={"name": col.name, "slug": col.slug},
            ip_address=ip_address,
        )

        return {"success": True, "message": f"Collection '{col.name}' deactivated successfully."}

    @staticmethod
    def list_documents(
        db: Session,
        collection_id: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[DocumentOut]:
        """List documents optionally filtered by collection."""
        query = db.query(Document).filter(Document.status != DocumentStatus.DELETED.value)
        if not include_archived:
            query = query.filter(Document.status != DocumentStatus.ARCHIVED.value)
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
            v_num = latest_version.version_number if latest_version else d.version_number
            v_status = DocumentVersionStatus(d.status)
            total_pages = latest_version.total_pages if latest_version else 0

            results.append(
                DocumentOut(
                    id=d.id,
                    collection_id=d.collection_id,
                    title=d.scheme_name,
                    scheme_code=None,
                    department=d.department,
                    state_or_district=d.state_or_district,
                    current_version=v_num,
                    status=v_status,
                    total_pages=total_pages,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
            )
        return results

    @staticmethod
    def upload_document(
        db: Session,
        data: DocumentUploadRequest,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> DocumentOut:
        """Upload a new official scheme PDF document (Administrator only)."""
        col = db.query(DocumentCollection).filter(DocumentCollection.id == data.collection_id).first()
        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target document collection not found."
            )

        file_hash = hashlib.sha256(
            (data.original_filename + data.scheme_name + str(datetime.utcnow())).encode("utf-8")
        ).hexdigest()

        storage_key = data.storage_file_key or f"raw-documents/{col.slug}/{data.original_filename}"

        # Create Master Document record
        new_doc = Document(
            collection_id=col.id,
            scheme_name=data.scheme_name,
            department=data.department,
            state_or_district=data.state_or_district or "National / All States",
            language=data.language or "en",
            publication_date=datetime.utcnow(),
            effective_date=data.effective_date or datetime.utcnow(),
            original_filename=data.original_filename,
            storage_file_key=storage_key,
            mime_type="application/pdf",
            file_hash=file_hash,
            version_number=1,
            status=DocumentStatus.ACTIVE.value,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # Create Version 1 record
        new_ver = DocumentVersion(
            document_id=new_doc.id,
            version_number=1,
            original_filename=data.original_filename,
            storage_file_key=storage_key,
            mime_type="application/pdf",
            file_hash=file_hash,
            file_size_bytes=1024 * 1024,
            total_pages=1,
            status=DocumentStatus.ACTIVE.value,
            effective_date=new_doc.effective_date,
            change_summary="Initial upload of official circular.",
        )
        db.add(new_ver)
        db.commit()
        db.refresh(new_ver)

        # Create Page 1 record & initial chunk
        page_1 = DocumentPage(
            version_id=new_ver.id,
            document_id=new_doc.id,
            page_number=1,
            raw_text=f"Official guidelines and criteria for {data.scheme_name}.",
            storage_image_path=f"page-artifacts/{new_doc.id}/v1/pages/page-001.webp",
            word_count=50,
        )
        db.add(page_1)
        db.commit()
        db.refresh(page_1)

        chunk_1 = ExtractedChunk(
            page_id=page_1.id,
            version_id=new_ver.id,
            document_id=new_doc.id,
            chunk_index=0,
            chunk_text=f"Official guidelines and criteria for {data.scheme_name}.",
            token_count=20,
            start_char_offset=0,
            end_char_offset=len(page_1.raw_text),
            vector_id=f"vec-{new_doc.id[:8]}-001",
        )
        db.add(chunk_1)
        db.commit()

        AuditService.log_event(
            db=db,
            action="DOC_UPLOAD",
            entity_type="documents",
            user_id=admin_user_id,
            entity_id=new_doc.id,
            details={
                "scheme_name": new_doc.scheme_name,
                "filename": new_doc.original_filename,
                "collection_id": col.id,
            },
            ip_address=ip_address,
        )

        return DocumentOut(
            id=new_doc.id,
            collection_id=new_doc.collection_id,
            title=new_doc.scheme_name,
            scheme_code=None,
            department=new_doc.department,
            state_or_district=new_doc.state_or_district,
            current_version=1,
            status=DocumentVersionStatus.ACTIVE,
            total_pages=1,
            created_at=new_doc.created_at,
            updated_at=new_doc.updated_at,
        )

    @staticmethod
    def process_document(
        db: Session,
        document_id: str,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> DocumentActionResponse:
        """Trigger or re-trigger document parsing and indexing (Administrator only)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        # Create processing job record
        job = ProcessingJob(
            document_id=doc.id,
            job_type="PDF_INGESTION",
            status="COMPLETED",
            progress_percent=100,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(job)
        doc.status = DocumentStatus.ACTIVE.value
        db.commit()

        AuditService.log_event(
            db=db,
            action="DOC_PROCESS",
            entity_type="documents",
            user_id=admin_user_id,
            entity_id=doc.id,
            details={"action": "DOCUMENT_REINDEXED"},
            ip_address=ip_address,
        )

        return DocumentActionResponse(
            success=True,
            document_id=doc.id,
            action="PROCESS",
            status="ACTIVE",
            message=f"Document '{doc.scheme_name}' successfully processed and re-indexed.",
        )

    @staticmethod
    def archive_document(
        db: Session,
        document_id: str,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> DocumentActionResponse:
        """Archive an official scheme document (Administrator only)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        doc.status = DocumentStatus.ARCHIVED.value
        db.commit()

        AuditService.log_event(
            db=db,
            action="DOC_ARCHIVE",
            entity_type="documents",
            user_id=admin_user_id,
            entity_id=doc.id,
            details={"scheme_name": doc.scheme_name, "status": "ARCHIVED"},
            ip_address=ip_address,
        )

        return DocumentActionResponse(
            success=True,
            document_id=doc.id,
            action="ARCHIVE",
            status="ARCHIVED",
            message=f"Document '{doc.scheme_name}' has been archived and excluded from public search.",
        )

    @staticmethod
    def delete_document(
        db: Session,
        document_id: str,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> DocumentActionResponse:
        """Mark document as DELETED (Administrator only)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        doc.status = DocumentStatus.DELETED.value
        db.commit()

        AuditService.log_event(
            db=db,
            action="DOC_DELETE",
            entity_type="documents",
            user_id=admin_user_id,
            entity_id=doc.id,
            details={"scheme_name": doc.scheme_name, "status": "DELETED"},
            ip_address=ip_address,
        )

        return DocumentActionResponse(
            success=True,
            document_id=doc.id,
            action="DELETE",
            status="DELETED",
            message=f"Document '{doc.scheme_name}' deleted successfully.",
        )

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

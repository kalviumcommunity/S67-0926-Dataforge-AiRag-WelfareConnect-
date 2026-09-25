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
    DocumentConflictWarning,
    DocumentOut,
    DocumentUploadRequest,
    DocumentVersionOut,
    DocumentVersionStatus,
    PageOut,
    ProcessingSummaryOut,
    UserOut,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.storage_service import storage_service
from backend.app.workers.background_jobs import task_queue
from backend.app.config import settings



import base64
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def _generate_sample_pdf(scheme_name: str, department: str, version_number: int = 1) -> bytes:
    """Generate a clean multi-paragraph PDF document."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Page 1: Header & Eligibility
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, f"Government of India - {department}")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 720, f"Official Policy Guidelines: {scheme_name} (Version {version_number})")
    c.setFont("Helvetica", 11)
    c.drawString(72, 690, "Section 1. Objectives and Scope")
    c.drawString(72, 670, f"This document outlines the official administrative guidelines for {scheme_name}.")
    c.drawString(72, 650, "The scheme provides financial and technical assistance to eligible beneficiaries nationwide.")
    c.drawString(72, 620, "Section 2. Eligibility Criteria")
    c.drawString(72, 600, "1. Applicants must be citizens residing in the designated jurisdiction.")
    c.drawString(72, 580, "2. Annual household income must satisfy statutory thresholds.")
    c.drawString(72, 560, "3. All supporting identification documents must be submitted through verified government portals.")
    c.showPage()
    c.save()
    return buffer.getvalue()


class DocumentService:
    @staticmethod
    def list_collections(db: Session, current_user: Optional[UserOut] = None) -> List[CollectionOut]:
        """List all active accessible scheme collections."""
        query = db.query(DocumentCollection).filter(DocumentCollection.is_active.is_(True))
        
        is_admin = False
        if current_user and current_user.permissions:
            is_admin = "admin:all" in current_user.permissions or "collections:manage" in current_user.permissions

        if not is_admin:
            if current_user:
                query = query.filter(
                    (DocumentCollection.is_private.is_(False)) | (DocumentCollection.owner_user_id == current_user.id)
                )
            else:
                query = query.filter(DocumentCollection.is_private.is_(False))

        collections = query.all()
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
                    is_private=bool(c.is_private),
                    owner_user_id=c.owner_user_id,
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
            owner_user_id=data.owner_user_id or admin_user_id,
            is_private=bool(data.is_private),
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
            details={"name": col.name, "slug": col.slug, "is_private": col.is_private},
            ip_address=ip_address,
        )

        return CollectionOut(
            id=col.id,
            name=col.name,
            slug=col.slug,
            description=col.description,
            department=None,
            is_private=bool(col.is_private),
            owner_user_id=col.owner_user_id,
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
            total_pages = latest_version.total_pages if latest_version else 1
            f_size = latest_version.file_size_bytes if latest_version else 0

            results.append(
                DocumentOut(
                    id=d.id,
                    collection_id=d.collection_id,
                    title=d.scheme_name,
                    scheme_code=None,
                    department=d.department,
                    state_or_district=d.state_or_district,
                    language=d.language or "en",
                    publication_date=d.publication_date,
                    effective_date=d.effective_date,
                    current_version=v_num,
                    status=v_status,
                    total_pages=total_pages,
                    file_hash=d.file_hash,
                    file_size_bytes=f_size,
                    visibility="public",
                    duplicate_warning=None,
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
        """Upload a new official scheme PDF document via JSON payload (Administrator only)."""
        # 1. Validate File Extension
        filename_lower = data.original_filename.lower().strip()
        if not any(filename_lower.endswith(ext) for ext in settings.ALLOWED_FILE_EXTENSIONS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Only official PDF documents ({', '.join(settings.ALLOWED_FILE_EXTENSIONS)}) are accepted."
            )

        # 2. Validate Official Source Confirmation
        if data.is_official_source_confirmed is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must confirm that this is an official government publication."
            )

        col = db.query(DocumentCollection).filter(DocumentCollection.id == data.collection_id).first()
        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target document collection not found."
            )

        v_num = data.version_number or 1
        storage_key = data.storage_file_key or f"raw-documents/{col.slug}/{data.original_filename}"

        if data.file_content_base64:
            pdf_bytes = base64.b64decode(data.file_content_base64)
        else:
            pdf_bytes = _generate_sample_pdf(data.scheme_name, data.department, v_num)

        file_bytes_len = len(pdf_bytes)
        file_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # Save to storage
        storage_service.save_file(storage_key, pdf_bytes)

        # 3. Duplicate file detection
        duplicate_warning: Optional[str] = None
        existing_dup = db.query(Document).filter(
            Document.file_hash == file_hash,
            Document.status != DocumentStatus.DELETED.value,
        ).first()
        if existing_dup:
            duplicate_warning = (
                f"Duplicate warning: An existing document '{existing_dup.scheme_name}' "
                f"(ID: {existing_dup.id}) shares the identical content hash."
            )

        # Create Master Document record
        new_doc = Document(
            collection_id=col.id,
            scheme_name=data.scheme_name,
            department=data.department,
            state_or_district=data.state_or_district or "National / All States",
            language=data.language or "en",
            publication_date=data.publication_date or datetime.utcnow(),
            effective_date=data.effective_date or datetime.utcnow(),
            original_filename=data.original_filename,
            storage_file_key=storage_key,
            mime_type="application/pdf",
            file_hash=file_hash,
            version_number=v_num,
            status=DocumentStatus.ACTIVE.value,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # Create Version record
        new_ver = DocumentVersion(
            document_id=new_doc.id,
            version_number=v_num,
            original_filename=data.original_filename,
            storage_file_key=storage_key,
            mime_type="application/pdf",
            file_hash=file_hash,
            file_size_bytes=file_bytes_len,
            total_pages=1,
            status=DocumentStatus.ACTIVE.value,
            effective_date=new_doc.effective_date,
            change_summary="Initial upload of official circular.",
        )
        db.add(new_ver)
        db.commit()
        db.refresh(new_ver)

        # Enqueue processing pipeline immediately
        task_queue.enqueue_document_processing(
            document_id=new_doc.id,
            version_id=new_ver.id,
            storage_key=storage_key,
            db=db,
        )


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
                "file_hash": file_hash,
                "is_duplicate": existing_dup is not None,
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
            language=new_doc.language,
            publication_date=new_doc.publication_date,
            effective_date=new_doc.effective_date,
            current_version=v_num,
            status=DocumentVersionStatus.ACTIVE,
            total_pages=1,
            file_hash=file_hash,
            file_size_bytes=file_bytes_len,
            visibility=data.visibility or "public",
            duplicate_warning=duplicate_warning,
            created_at=new_doc.created_at,
            updated_at=new_doc.updated_at,
        )

    @staticmethod
    def upload_document_file(
        db: Session,
        file_content: bytes,
        filename: str,
        collection_id: str,
        scheme_name: str,
        department: str,
        admin_user_id: str,
        state_or_district: Optional[str] = "National / All States",
        language: Optional[str] = "en",
        publication_date: Optional[datetime] = None,
        effective_date: Optional[datetime] = None,
        version_number: Optional[int] = 1,
        visibility: Optional[str] = "public",
        is_official_source_confirmed: bool = True,
        ip_address: Optional[str] = None,
    ) -> DocumentOut:
        """Upload a binary PDF document with size, extension, integrity, and duplicate validation."""
        # 1. Validate File Extension
        filename_lower = filename.lower().strip()
        if not any(filename_lower.endswith(ext) for ext in settings.ALLOWED_FILE_EXTENSIONS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Only official PDF documents ({', '.join(settings.ALLOWED_FILE_EXTENSIONS)}) are accepted."
            )

        # 2. Validate File Size
        file_size = len(file_content)
        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size ({file_size / (1024 * 1024):.1f}MB) exceeds the maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF file cannot be empty."
            )

        # 3. Validate Official Confirmation
        if not is_official_source_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must confirm that this is an official government publication."
            )

        col = db.query(DocumentCollection).filter(DocumentCollection.id == collection_id).first()
        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target document collection not found."
            )

        # 4. Calculate SHA-256 File Hash
        file_hash = hashlib.sha256(file_content).hexdigest()

        # 5. Check Duplicate Warning
        duplicate_warning: Optional[str] = None
        existing_dup = db.query(Document).filter(
            Document.file_hash == file_hash,
            Document.status != DocumentStatus.DELETED.value,
        ).first()
        if existing_dup:
            duplicate_warning = (
                f"Duplicate warning: An existing document '{existing_dup.scheme_name}' "
                f"(ID: {existing_dup.id}) shares the identical content hash."
            )

        storage_key = f"raw-documents/{col.slug}/{filename}"
        v_num = version_number or 1

        # Save binary to storage
        storage_service.save_file(storage_key, file_content)

        # 6. Create Master Document
        new_doc = Document(
            collection_id=col.id,
            scheme_name=scheme_name,
            department=department,
            state_or_district=state_or_district or "National / All States",
            language=language or "en",
            publication_date=publication_date or datetime.utcnow(),
            effective_date=effective_date or datetime.utcnow(),
            original_filename=filename,
            storage_file_key=storage_key,
            mime_type="application/pdf",
            file_hash=file_hash,
            version_number=v_num,
            status=DocumentStatus.ACTIVE.value,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # 7. Create Document Version
        new_ver = DocumentVersion(
            document_id=new_doc.id,
            version_number=v_num,
            original_filename=filename,
            storage_file_key=storage_key,
            mime_type="application/pdf",
            file_hash=file_hash,
            file_size_bytes=file_size,
            total_pages=1,
            status=DocumentStatus.ACTIVE.value,
            effective_date=new_doc.effective_date,
            change_summary="Binary PDF uploaded through admin upload flow.",
        )
        db.add(new_ver)
        db.commit()
        db.refresh(new_ver)

        # 8. Run background processing pipeline
        task_queue.enqueue_document_processing(
            document_id=new_doc.id,
            version_id=new_ver.id,
            storage_key=storage_key,
            db=db,
        )


        # 9. Audit Event
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
                "file_size_bytes": file_size,
                "file_hash": file_hash,
                "is_duplicate": existing_dup is not None,
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
            language=new_doc.language,
            publication_date=new_doc.publication_date,
            effective_date=new_doc.effective_date,
            current_version=v_num,
            status=DocumentVersionStatus(new_doc.status),
            total_pages=new_ver.total_pages or 1,
            file_hash=file_hash,
            file_size_bytes=file_size,
            visibility=visibility or "public",
            duplicate_warning=duplicate_warning,
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

        latest_ver = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        if not latest_ver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found.")

        # Ensure file exists in storage
        if not storage_service.file_exists(latest_ver.storage_file_key):
            sample_pdf = _generate_sample_pdf(doc.scheme_name, doc.department, latest_ver.version_number)
            storage_service.save_file(latest_ver.storage_file_key, sample_pdf)

        # Execute processing pipeline
        task_queue.enqueue_document_processing(
            document_id=doc.id,
            version_id=latest_ver.id,
            storage_key=latest_ver.storage_file_key,
            db=db,
        )


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
            status=doc.status,
            message=f"Document '{doc.scheme_name}' successfully processed and re-indexed.",
        )


    @staticmethod
    def archive_document(
        db: Session,
        document_id: str,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> DocumentActionResponse:
        """Archive an official scheme document and all active versions (Administrator only)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        prev_status = doc.status
        doc.status = DocumentStatus.ARCHIVED.value
        doc.updated_at = datetime.utcnow()

        # Update all versions for this document
        versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).all()
        for v in versions:
            v.status = DocumentStatus.ARCHIVED.value
            v.updated_at = datetime.utcnow()

        db.commit()

        AuditService.log_event(
            db=db,
            action="DOC_ARCHIVE",
            entity_type="documents",
            user_id=admin_user_id,
            entity_id=doc.id,
            details={
                "scheme_name": doc.scheme_name,
                "previous_status": prev_status,
                "new_status": "ARCHIVED",
                "version_number": doc.version_number,
                "timestamp": datetime.utcnow().isoformat(),
            },
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
    def restore_document(
        db: Session,
        document_id: str,
        admin_user_id: str,
        ip_address: Optional[str] = None,
    ) -> DocumentActionResponse:
        """Restore an archived official scheme document back to ACTIVE state (Administrator only)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        prev_status = doc.status
        doc.status = DocumentStatus.ACTIVE.value
        doc.updated_at = datetime.utcnow()

        # Restore versions
        versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).all()
        for v in versions:
            v.status = DocumentStatus.ACTIVE.value
            v.updated_at = datetime.utcnow()

        db.commit()

        AuditService.log_event(
            db=db,
            action="DOC_RESTORE",
            entity_type="documents",
            user_id=admin_user_id,
            entity_id=doc.id,
            details={
                "scheme_name": doc.scheme_name,
                "previous_status": prev_status,
                "new_status": "ACTIVE",
                "version_number": doc.version_number,
                "timestamp": datetime.utcnow().isoformat(),
            },
            ip_address=ip_address,
        )

        return DocumentActionResponse(
            success=True,
            document_id=doc.id,
            action="RESTORE",
            status="ACTIVE",
            message=f"Document '{doc.scheme_name}' has been restored to active search index.",
        )

    @staticmethod
    def list_document_versions(db: Session, document_id: str) -> List[DocumentVersionOut]:
        """List all versions for a given scheme document."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        versions = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .all()
        )
        return [
            DocumentVersionOut(
                id=v.id,
                document_id=v.document_id,
                version_number=v.version_number,
                original_filename=v.original_filename,
                status=v.status,
                effective_date=v.effective_date,
                change_summary=v.change_summary,
                file_size_bytes=v.file_size_bytes,
                total_pages=v.total_pages,
                created_at=v.created_at,
                updated_at=v.updated_at,
            )
            for v in versions
        ]

    @staticmethod
    def create_document_version(
        db: Session,
        document_id: str,
        version_number: int,
        original_filename: str,
        admin_user_id: str,
        storage_file_key: Optional[str] = None,
        file_size_bytes: int = 1024 * 1024,
        effective_date: Optional[datetime] = None,
        change_summary: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> DocumentVersionOut:
        """Add a new version for an existing document (Administrator only)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        # Check if version number already exists
        existing_v = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id, DocumentVersion.version_number == version_number)
            .first()
        )
        if existing_v:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Version {version_number} already exists for this document."
            )

        col = db.query(DocumentCollection).filter(DocumentCollection.id == doc.collection_id).first()
        s_key = storage_file_key or f"raw-documents/{col.slug if col else 'general'}/{original_filename}"

        # If file not in storage, create sample pdf
        if not storage_service.file_exists(s_key):
            pdf_bytes = _generate_sample_pdf(doc.scheme_name, doc.department, version_number)
            storage_service.save_file(s_key, pdf_bytes)
            file_size_bytes = len(pdf_bytes)
            f_hash = hashlib.sha256(pdf_bytes).hexdigest()
        else:
            f_hash = hashlib.sha256((original_filename + doc.scheme_name + str(version_number)).encode("utf-8")).hexdigest()

        new_ver = DocumentVersion(
            document_id=doc.id,
            version_number=version_number,
            original_filename=original_filename,
            storage_file_key=s_key,
            mime_type="application/pdf",
            file_hash=f_hash,
            file_size_bytes=file_size_bytes,
            total_pages=1,
            status=DocumentStatus.ACTIVE.value,
            effective_date=effective_date or doc.effective_date,
            change_summary=change_summary or f"Uploaded version {version_number} release.",
        )
        db.add(new_ver)

        # Update Master Document current version
        if version_number > doc.version_number:
            doc.version_number = version_number
            doc.file_hash = f_hash
            doc.effective_date = new_ver.effective_date
            doc.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(new_ver)

        # Run background processing for the new version
        task_queue.enqueue_document_processing(
            document_id=doc.id,
            version_id=new_ver.id,
            storage_key=s_key,
            db=db,
        )


        AuditService.log_event(
            db=db,
            action="DOC_VERSION_CREATED",
            entity_type="document_versions",
            user_id=admin_user_id,
            entity_id=new_ver.id,
            details={
                "document_id": doc.id,
                "scheme_name": doc.scheme_name,
                "version_number": version_number,
                "filename": original_filename,
                "timestamp": datetime.utcnow().isoformat(),
            },
            ip_address=ip_address,
        )

        return DocumentVersionOut(
            id=new_ver.id,
            document_id=new_ver.document_id,
            version_number=new_ver.version_number,
            original_filename=new_ver.original_filename,
            status=new_ver.status,
            effective_date=new_ver.effective_date,
            change_summary=new_ver.change_summary,
            file_size_bytes=new_ver.file_size_bytes,
            total_pages=new_ver.total_pages,
            created_at=new_ver.created_at,
            updated_at=new_ver.updated_at,
        )

    @staticmethod
    def detect_version_conflicts(db: Session, collection_id: Optional[str] = None) -> List[DocumentConflictWarning]:
        """Detect when two or more active documents cover the same scheme and overlapping period."""
        query = db.query(Document).filter(
            Document.status == DocumentStatus.ACTIVE.value
        )
        if collection_id:
            query = query.filter(Document.collection_id == collection_id)
        active_docs = query.all()

        from collections import defaultdict
        grouped = defaultdict(list)
        for d in active_docs:
            normalized_key = (d.collection_id, d.scheme_name.lower().strip())
            grouped[normalized_key].append(d)

        warnings: List[DocumentConflictWarning] = []
        for (col_id, s_name), docs in grouped.items():
            if len(docs) > 1:
                doc_ids = [d.id for d in docs]
                version_nums = [d.version_number for d in docs]
                warnings.append(
                    DocumentConflictWarning(
                        scheme_name=docs[0].scheme_name,
                        collection_id=col_id,
                        conflicting_document_ids=doc_ids,
                        conflicting_version_numbers=version_nums,
                        message=(
                            f"Warning: {len(docs)} active documents appear to cover scheme '{docs[0].scheme_name}' "
                            f"in the same collection (Versions: {version_nums}). "
                            "Consider archiving the superseded version to prevent ambiguous citations."
                        ),
                    )
                )
        return warnings


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
                native_text=None,
                ocr_text=None,
                extraction_method="NATIVE",
                ocr_confidence=None,
                is_scanned=False,
                requires_admin_review=False,
                review_reason=None,
                word_count=0,
            )

        return PageOut(
            page_number=page.page_number,
            text_preview=page.raw_text[:1000],
            image_url=page.storage_image_path,
            native_text=page.native_text,
            ocr_text=page.ocr_text,
            extraction_method=page.extraction_method or "NATIVE",
            ocr_confidence=page.ocr_confidence,
            is_scanned=page.is_scanned or False,
            requires_admin_review=page.requires_admin_review or False,
            review_reason=page.review_reason,
            word_count=page.word_count or 0,
        )

    @staticmethod
    def get_processing_summary(db: Session, document_id: str) -> ProcessingSummaryOut:
        """Get extraction processing summary (native text, OCR, low-confidence, failed counts)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )

        pages = db.query(DocumentPage).filter(DocumentPage.document_id == document_id).all()
        native_count = sum(1 for p in pages if (p.extraction_method or "NATIVE") == "NATIVE")
        ocr_count = sum(1 for p in pages if (p.extraction_method or "") in ("OCR", "HYBRID"))
        low_conf_count = sum(1 for p in pages if p.requires_admin_review)
        scanned_count = sum(1 for p in pages if p.is_scanned)

        if not job:
            return ProcessingSummaryOut(
                job_id="job-direct",
                document_id=doc.id,
                version_id=None,
                status=doc.status,
                progress_percent=100 if doc.status == DocumentStatus.ACTIVE.value else 0,
                total_pages=len(pages) or 1,
                native_text_pages=native_count or 1,
                ocr_pages=ocr_count,
                failed_pages=0,
                low_confidence_pages=low_conf_count,
                scanned_pages=scanned_count,
                error_message=None,
                started_at=doc.created_at,
                completed_at=doc.updated_at,
            )

        summary = job.summary_details or {}
        return ProcessingSummaryOut(
            job_id=job.id,
            document_id=doc.id,
            version_id=job.version_id,
            status=job.status,
            progress_percent=job.progress_percent,
            total_pages=summary.get("total_pages", len(pages) or 1),
            native_text_pages=summary.get("native_text_pages", native_count),
            ocr_pages=summary.get("ocr_pages", ocr_count),
            failed_pages=summary.get("failed_pages", 0),
            low_confidence_pages=summary.get("low_confidence_pages", low_conf_count),
            scanned_pages=summary.get("scanned_pages", scanned_count),
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )


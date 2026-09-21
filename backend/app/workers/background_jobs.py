"""
Background job dispatcher, task queue, and document processing pipeline orchestrator.
Manages retryable document processing, status synchronization, and database persistence.
"""

from datetime import datetime
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.db_models import (
    AuditEvent,
    Document,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    ProcessingJob,
)
from backend.app.services.indexing_service import IndexingService, indexing_service
from backend.app.services.storage_service import storage_service
from backend.app.workers.document_processor import DocumentProcessor, ProcessingPipelineResult

logger = logging.getLogger(__name__)


class DocumentProcessingOrchestrator:
    @classmethod
    def execute_with_retries(
        cls,
        document_id: str,
        version_id: str,
        storage_key: str,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Execute document processing pipeline with exponential backoff retries for transient errors.
        """
        attempt = 0
        last_exception: Optional[Exception] = None
        is_managed_db = db is None

        while attempt < max_retries:
            attempt += 1
            session: Session = db if db is not None else SessionLocal()
            try:
                # 1. Fetch document and version records
                doc = session.query(Document).filter(Document.id == document_id).first()
                ver = session.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
                if not doc or not ver:
                    raise ValueError(f"Document {document_id} or Version {version_id} not found in database.")

                # 2. Get or create processing job
                job = (
                    session.query(ProcessingJob)
                    .filter(ProcessingJob.document_id == document_id, ProcessingJob.version_id == version_id)
                    .order_by(ProcessingJob.created_at.desc())
                    .first()
                )
                if not job:
                    job = ProcessingJob(
                        document_id=document_id,
                        version_id=version_id,
                        job_type="PDF_INGESTION",
                        status="RUNNING",
                        progress_percent=10,
                        started_at=datetime.utcnow(),
                    )
                    session.add(job)
                else:
                    job.status = "RUNNING"
                    job.progress_percent = 10
                    job.started_at = datetime.utcnow()
                    job.error_message = None

                session.commit()

                # 3. Retrieve / Download file from storage
                job.progress_percent = 25
                session.commit()

                try:
                    file_bytes = storage_service.download_file(storage_key)
                except FileNotFoundError as fnf:
                    # Non-retryable: file missing in storage
                    raise ValueError(f"Document file missing in storage: {fnf}") from fnf

                # 4. Process document bytes
                job.progress_percent = 45
                session.commit()

                result: ProcessingPipelineResult = DocumentProcessor.process_document_bytes(
                    file_bytes=file_bytes,
                    document_id=document_id,
                    version_id=version_id,
                )

                if not result.success:
                    # PDF validation failure (non-retryable)
                    job.status = "FAILED"
                    job.progress_percent = 100
                    job.error_message = result.error_message
                    job.completed_at = datetime.utcnow()
                    doc.status = DocumentStatus.FAILED.value
                    ver.status = DocumentStatus.FAILED.value
                    ver.error_message = result.error_message
                    session.commit()
                    return {
                        "success": False,
                        "error": result.error_message,
                        "document_id": document_id,
                        "attempts": attempt,
                    }

                # 5. Clear any existing pages & chunks for this version (idempotent re-runs)
                session.query(ExtractedChunk).filter(ExtractedChunk.version_id == version_id).delete()
                session.query(DocumentPage).filter(DocumentPage.version_id == version_id).delete()
                session.commit()

                # 6. Persist Document Pages and Extracted Chunks
                job.progress_percent = 70
                session.commit()

                chunk_payloads_for_indexing: List[Dict[str, Any]] = []

                for p in result.pages:
                    db_page = DocumentPage(
                        version_id=version_id,
                        document_id=document_id,
                        page_number=p.page_number,
                        raw_text=p.raw_text,
                        native_text=p.native_text,
                        ocr_text=p.ocr_text,
                        extraction_method=p.extraction_method,
                        ocr_confidence=p.ocr_confidence,
                        is_scanned=p.is_scanned,
                        requires_admin_review=p.requires_admin_review,
                        review_reason=p.review_reason,
                        storage_image_path=f"page-artifacts/{document_id}/v{ver.version_number}/pages/page-{p.page_number:03d}.webp",
                        word_count=p.word_count,
                    )
                    session.add(db_page)
                    session.flush()  # Get db_page.id

                    for c in p.chunks:
                        vec_id = IndexingService.generate_vector_id(
                            version_id=version_id,
                            page_number=p.page_number,
                            chunk_index=c.chunk_index,
                        )
                        chunk_meta = {
                            "collection_id": str(doc.collection_id),
                            "document_id": str(doc.id),
                            "document_version_id": str(ver.id),
                            "version_id": str(ver.id),
                            "page_number": int(p.page_number),
                            "page_range": str(c.page_range or p.page_number),
                            "scheme": str(doc.scheme_name),
                            "scheme_name": str(doc.scheme_name),
                            "department": str(doc.department),
                            "state_or_district": str(doc.state_or_district),
                            "language": str(doc.language),
                            "effective_date": str(ver.effective_date or doc.effective_date) if (ver.effective_date or doc.effective_date) else None,
                            "active": bool(ver.status == DocumentStatus.ACTIVE.value or doc.status == DocumentStatus.ACTIVE.value),
                            "is_active": bool(ver.status == DocumentStatus.ACTIVE.value or doc.status == DocumentStatus.ACTIVE.value),
                            "embedding_model": str(settings.EMBEDDING_MODEL),
                            "embedding_dimension": int(settings.EMBEDDING_DIMENSION),
                            "chunk_index": int(c.chunk_index),
                            "section_heading": str(c.section_heading or ""),
                            "extraction_method": str(p.extraction_method),
                        }
                        # Merge any existing chunk-level metadata
                        if hasattr(c, "metadata") and c.metadata:
                            chunk_meta.update(c.metadata)

                        now_dt = datetime.utcnow()
                        db_chunk = ExtractedChunk(
                            page_id=db_page.id,
                            version_id=version_id,
                            document_id=document_id,
                            chunk_index=c.chunk_index,
                            page_number=c.page_number,
                            page_range=c.page_range,
                            section_heading=c.section_heading,
                            chunk_text=c.chunk_text,
                            normalized_text=c.normalized_text,
                            token_count=c.token_count,
                            start_char_offset=c.start_char_offset,
                            end_char_offset=c.end_char_offset,
                            metadata_json=chunk_meta,
                            vector_id=vec_id,
                            embedding_model=settings.EMBEDDING_MODEL,
                            embedding_dimension=settings.EMBEDDING_DIMENSION,
                            indexed_at=now_dt,
                        )
                        session.add(db_chunk)
                        chunk_payloads_for_indexing.append({
                            "chunk_id": db_chunk.id,
                            "page_number": p.page_number,
                            "page_range": c.page_range,
                            "section_heading": c.section_heading,
                            "chunk_index": c.chunk_index,
                            "chunk_text": c.chunk_text,
                            "normalized_text": c.normalized_text,
                            "token_count": c.token_count,
                            "vector_id": vec_id,
                            "metadata": chunk_meta,
                        })

                session.commit()

                # 7. Send only completed chunks to Indexing Service
                job.progress_percent = 90
                session.commit()

                indexing_service.index_chunks(
                    document_id=document_id,
                    version_id=version_id,
                    chunks=chunk_payloads_for_indexing,
                    collection_id=doc.collection_id,
                )

                # 8. Mark job & document status as COMPLETED / ACTIVE
                summary = {
                    "total_pages": result.total_pages,
                    "native_text_pages": result.native_text_pages,
                    "ocr_pages": result.ocr_pages,
                    "failed_pages": result.failed_pages,
                    "low_confidence_pages": result.low_confidence_pages,
                    "scanned_pages": result.scanned_pages,
                    "chunks_count": len(chunk_payloads_for_indexing),
                    "execution_attempts": attempt,
                }

                job.status = "COMPLETED"
                job.progress_percent = 100
                job.completed_at = datetime.utcnow()
                job.summary_details = summary

                ver.total_pages = result.total_pages
                ver.status = DocumentStatus.ACTIVE.value
                ver.error_message = None

                doc.status = DocumentStatus.ACTIVE.value

                # Create Audit log
                audit = AuditEvent(
                    action_type="DOC_PROCESS_COMPLETED",
                    entity_table="documents",
                    entity_id=document_id,
                    metadata_json=summary,
                )
                session.add(audit)
                session.commit()

                return {
                    "success": True,
                    "document_id": document_id,
                    "version_id": version_id,
                    "summary": summary,
                    "attempts": attempt,
                }

            except ValueError as ve:
                # Permanent non-retryable validation error
                logger.error(f"Permanent validation error processing document {document_id}: {ve}")
                cls._mark_failed(session, document_id, version_id, str(ve))
                return {"success": False, "error": str(ve), "document_id": document_id, "attempts": attempt}

            except Exception as exc:
                last_exception = exc
                logger.warning(
                    f"Transient error processing document {document_id} (Attempt {attempt}/{max_retries}): {exc}"
                )
                if attempt < max_retries:
                    sleep_time = backoff_base * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
            finally:
                if is_managed_db:
                    session.close()

        # All retries exhausted
        err_msg = f"Document processing failed after {max_retries} attempts: {last_exception}"
        logger.error(err_msg)
        fail_session = db if db is not None else SessionLocal()
        try:
            cls._mark_failed(fail_session, document_id, version_id, err_msg)
        finally:
            if is_managed_db:
                fail_session.close()

        return {"success": False, "error": err_msg, "document_id": document_id, "attempts": max_retries}

    @staticmethod
    def _mark_failed(db: Session, document_id: str, version_id: str, error_message: str):
        """Mark document, version, and job as FAILED."""
        try:
            job = (
                db.query(ProcessingJob)
                .filter(ProcessingJob.document_id == document_id, ProcessingJob.version_id == version_id)
                .order_by(ProcessingJob.created_at.desc())
                .first()
            )
            if job:
                job.status = "FAILED"
                job.progress_percent = 100
                job.error_message = error_message
                job.completed_at = datetime.utcnow()

            ver = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
            if ver:
                ver.status = DocumentStatus.FAILED.value
                ver.error_message = error_message

            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED.value

            audit = AuditEvent(
                action_type="DOC_PROCESS_FAILED",
                entity_table="documents",
                entity_id=document_id,
                metadata_json={"error": error_message},
            )
            db.add(audit)
            db.commit()

        except Exception as e:
            logger.error(f"Failed to record failure state in db: {e}")


class TaskQueue:
    """In-process and background task queue."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def enqueue_document_processing(
        self,
        document_id: str,
        version_id: str,
        storage_key: str,
        db: Optional[Session] = None,
    ) -> str:
        """Enqueue document processing task."""
        job_id = f"job-{uuid.uuid4()}"
        self.tasks[job_id] = {
            "id": job_id,
            "document_id": document_id,
            "version_id": version_id,
            "status": "QUEUED",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Run pipeline
        res = DocumentProcessingOrchestrator.execute_with_retries(
            document_id=document_id,
            version_id=version_id,
            storage_key=storage_key,
            max_retries=settings.MAX_PROCESSING_RETRIES,
            backoff_base=settings.RETRY_BACKOFF_BASE_SECONDS,
            db=db,
        )
        self.tasks[job_id]["result"] = res
        self.tasks[job_id]["status"] = "COMPLETED" if res.get("success") else "FAILED"
        return job_id


task_queue = TaskQueue()

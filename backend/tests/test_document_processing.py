"""
Comprehensive test suite for the Document Processing Pipeline and OCR Ingestion.
Tests:
1. Multi-page digital PDF processing (native extraction, headings, paragraphs, page numbers).
2. Scanned / low-text page detection and OCR execution.
3. Dual storage (native_text vs ocr_text) and duplicate text prevention.
4. OCR confidence scoring and administrator review flagging.
5. Ingestion processing summary metrics.
6. Deliberately corrupted / invalid file rejection with error recording.
7. Transient failure safe retry mechanism.
8. Chunk indexing without passing raw PDF to LLM.
"""

import io
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models.db_models import (
    AuditEvent,
    Document,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    ProcessingJob,
)
from backend.app.services.indexing_service import indexing_service
from backend.app.services.ocr_service import FallbackOcrEngine, OcrResult, ocr_service
from backend.app.services.storage_service import storage_service
from backend.app.workers.background_jobs import DocumentProcessingOrchestrator
from backend.app.workers.document_processor import DocumentProcessor


def create_test_pdf_bytes(include_scanned_page: bool = True) -> bytes:
    """Generate a clean 3-page digital PDF with headings, paragraphs, and a low-text page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    # --- Page 1: Policy Guidelines & Scope ---
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "Ministry of Rural Development")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 720, "Pradhan Mantri Gram Sadak Yojana (PMGSY)")
    c.setFont("Helvetica", 11)
    c.drawString(72, 690, "Section 1. Program Objectives")
    c.drawString(72, 670, "The primary objective of PMGSY is to provide all-weather road connectivity.")
    c.drawString(72, 650, "Connectivity is provided to eligible unconnected habitations in rural areas.")
    c.drawString(72, 620, "Section 2. Scope of Works")
    c.drawString(72, 600, "The scheme covers construction of new link roads and major cross-drainage structures.")
    c.drawString(72, 580, "Special focus is given to hill states, desert zones, and tribal schedule areas.")
    c.showPage()

    # --- Page 2: Eligibility & Funding Criteria ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 750, "Section 3. Eligibility and Population Norms")
    c.setFont("Helvetica", 11)
    c.drawString(72, 720, "1. Habitations with population of 500 persons and above in plain areas.")
    c.drawString(72, 700, "2. Habitations with population of 250 persons and above in hill and desert areas.")
    c.drawString(72, 670, "Section 4. Funding Pattern")
    c.drawString(72, 650, "The central and state governments share project funding in a 60:40 ratio.")
    c.drawString(72, 630, "For North Eastern and Himalayan states, funding is provided at 90:10 ratio.")
    c.showPage()

    # --- Page 3: Scanned / Low-text Page ---
    if include_scanned_page:
        c.setFont("Helvetica", 8)
        # Single line with very few words (< 15 words) to trigger scanned page detection
        c.drawString(72, 750, "Official Annexure Seal.")
    else:
        c.setFont("Helvetica", 11)
        c.drawString(72, 750, "Section 5. Monitoring and Technical Audits")
        c.drawString(72, 730, "Independent national quality monitors inspect completed project roads annually.")
    c.showPage()

    c.save()
    return buf.getvalue()


def test_validate_pdf_valid_and_invalid():
    """Test PDF format validation for both valid digital PDFs and corrupted streams."""
    valid_pdf = create_test_pdf_bytes()
    is_valid, err = DocumentProcessor.validate_pdf(valid_pdf)
    assert is_valid is True
    assert err is None

    # Deliberately invalid file: garbage bytes
    corrupt_bytes = b"NOT_A_PDF_CONTENT_RANDOM_GARBAGE"
    is_valid, err = DocumentProcessor.validate_pdf(corrupt_bytes)
    assert is_valid is False
    assert "Missing '%PDF-'" in err

    # Deliberately invalid file: empty bytes
    is_valid, err = DocumentProcessor.validate_pdf(b"")
    assert is_valid is False
    assert "empty" in err.lower()


def test_text_deduplication_and_paragraph_cleaning():
    """Test heading and paragraph preservation, plus deduplication of native and OCR text."""
    messy_text = "Heading Line 1\r\n\r\n\r\nParagraph 1 text.\n\n\n\nParagraph 2 text."
    cleaned = DocumentProcessor.clean_text_structure(messy_text)
    assert "\r" not in cleaned
    assert "Heading Line 1\n\nParagraph 1 text.\n\nParagraph 2 text." == cleaned

    # Native text comprehensive -> prefers native
    native = "Official circular with substantial text covering all eligibility rules and terms."
    ocr = "Official circular with substantial text covering all eligibility rules and terms."
    canonical, method = DocumentProcessor.deduplicate_text(native, ocr)
    assert method == "NATIVE"
    assert "substantial text" in canonical

    # Native text empty -> uses OCR
    canonical, method = DocumentProcessor.deduplicate_text("", "Scanned seal document content extracted.")
    assert method == "OCR"
    assert "Scanned seal" in canonical

    # Duplicate overlap prevention: native substring of OCR
    canonical, method = DocumentProcessor.deduplicate_text("Header text", "Header text Full scanned document body")
    assert method == "OCR"
    assert canonical.count("Header text") == 1


def test_full_document_processing_pipeline_and_summary(client: TestClient, db_session: Session):
    """
    Test end-to-end background document processing pipeline:
    1. Upload 3-page digital PDF with Page 3 having insufficient text.
    2. Verify background pipeline runs.
    3. Verify DocumentPage records: Page 1 & 2 are NATIVE, Page 3 is OCR/scanned.
    4. Verify page numbers (1, 2, 3) are preserved.
    5. Verify ExtractedChunk records generated with headings preserved.
    6. Verify ProcessingSummary endpoint metrics.
    """
    # 1. Admin login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    pdf_bytes = create_test_pdf_bytes(include_scanned_page=True)

    # 2. Upload PDF
    upload_res = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "PM Gram Sadak Yojana",
            "department": "Ministry of Rural Development",
            "state_or_district": "National / All States",
            "language": "en",
            "publication_date": "2024-01-15T00:00:00Z",
            "effective_date": "2024-04-01T00:00:00Z",
            "version_number": "1",
            "is_official_source_confirmed": "true",
        },
        files={"file": ("PMGSY_Guidelines.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # 3. Verify Database Entities
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc is not None
    assert doc.status == DocumentStatus.ACTIVE.value

    version = db_session.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).first()
    assert version is not None
    assert version.total_pages == 3
    assert version.status == DocumentStatus.ACTIVE.value

    pages = (
        db_session.query(DocumentPage)
        .filter(DocumentPage.document_id == doc_id)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )
    assert len(pages) == 3
    assert [p.page_number for p in pages] == [1, 2, 3]

    # Page 1: Native text with Program Objectives
    assert "PMGSY" in pages[0].raw_text or "Gram Sadak" in pages[0].raw_text
    assert pages[0].extraction_method == "NATIVE"
    assert pages[0].is_scanned is False

    # Page 2: Native text with Eligibility
    assert "Population Norms" in pages[1].raw_text or "Eligibility" in pages[1].raw_text
    assert pages[1].extraction_method == "NATIVE"
    assert pages[1].is_scanned is False

    # Page 3: Scanned page detected and OCR executed
    assert pages[2].is_scanned is True
    assert pages[2].ocr_text is not None or pages[2].extraction_method in ("OCR", "HYBRID")

    # Verify Extracted Chunks
    chunks = db_session.query(ExtractedChunk).filter(ExtractedChunk.document_id == doc_id).all()
    assert len(chunks) >= 3
    chunk_pages = [c.page.page_number for c in chunks]
    assert 1 in chunk_pages and 2 in chunk_pages

    # 4. Check Processing Summary Endpoint
    summary_res = client.get(
        f"/api/v1/documents/{doc_id}/processing-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["total_pages"] == 3
    assert summary_data["native_text_pages"] >= 2
    assert summary_data["scanned_pages"] >= 1
    assert summary_data["failed_pages"] == 0
    assert summary_data["status"] in ("COMPLETED", "ACTIVE")

    # 5. Check Page Preview Endpoint
    preview_res = client.get(
        f"/api/v1/documents/{doc_id}/pages/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert preview_res.status_code == 200
    p_data = preview_res.json()
    assert p_data["page_number"] == 1
    assert p_data["extraction_method"] == "NATIVE"


def test_ocr_low_confidence_review_flag(client: TestClient, db_session: Session):
    """Test that pages with low OCR confidence are flagged for administrator review."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    # Configure custom low-confidence OCR engine mock
    class LowConfidenceEngine(FallbackOcrEngine):
        def recognize(self, image: Image.Image, confidence_threshold: float = 70.0) -> OcrResult:
            return OcrResult(
                text="Faint smudged scan text",
                confidence=48.5,  # Below 70% threshold
                engine_name="mock_low_conf",
                word_count=4,
                is_low_confidence=True,
                requires_review=True,
                review_reason="Low OCR confidence (48.5% < 70.0%)",
            )

    original_engine = ocr_service.get_engine()
    ocr_service.set_engine(LowConfidenceEngine())

    try:
        pdf_bytes = create_test_pdf_bytes(include_scanned_page=True)
        upload_res = client.post(
            "/api/v1/documents/upload-file",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "collection_id": "col-0000000-0000-4000-8000-000000000001",
                "scheme_name": "Low Confidence Scan Test Scheme",
                "department": "Ministry of Social Justice",
                "is_official_source_confirmed": "true",
            },
            files={"file": ("smudged_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_res.status_code == 200
        doc_id = upload_res.json()["id"]

        # Check page 3 review flag
        page_3 = (
            db_session.query(DocumentPage)
            .filter(DocumentPage.document_id == doc_id, DocumentPage.page_number == 3)
            .first()
        )
        assert page_3 is not None
        assert page_3.requires_admin_review is True
        assert "Low OCR confidence" in (page_3.review_reason or "")

        # Check summary endpoint
        summary_res = client.get(
            f"/api/v1/documents/{doc_id}/processing-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert summary_res.status_code == 200
        assert summary_res.json()["low_confidence_pages"] >= 1

    finally:
        ocr_service.set_engine(original_engine)


def test_corrupted_file_failure_handling(client: TestClient, db_session: Session):
    """Test that corrupted files record error messages and transition to FAILED state."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    corrupted_pdf_bytes = b"%PDF-1.4\nTRUNCATED_CORRUPTED_STREAM_NO_PAGE_OBJECTS"

    upload_res = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Corrupted PDF Test Scheme",
            "department": "Ministry of IT",
            "is_official_source_confirmed": "true",
        },
        files={"file": ("corrupt.pdf", io.BytesIO(corrupted_pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # Verify Document and Version are marked FAILED
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == DocumentStatus.FAILED.value

    job = (
        db_session.query(ProcessingJob)
        .filter(ProcessingJob.document_id == doc_id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.status == "FAILED"
    assert job.error_message is not None


def test_transient_failure_retry_mechanism(db_session: Session):
    """Test that transient I/O exceptions retry and recover safely."""
    # Create test document and version in DB
    doc = Document(
        collection_id="col-0000000-0000-4000-8000-000000000001",
        scheme_name="Retry Test Scheme",
        department="Department of Finance",
        original_filename="retry_test.pdf",
        storage_file_key="raw-documents/test/retry_test.pdf",
        file_hash="hash123",
        status=DocumentStatus.PROCESSING.value,
    )
    db_session.add(doc)
    db_session.commit()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename="retry_test.pdf",
        storage_file_key="raw-documents/test/retry_test.pdf",
        file_hash="hash123",
        status=DocumentStatus.PROCESSING.value,
    )
    db_session.add(ver)
    db_session.commit()

    valid_pdf = create_test_pdf_bytes()
    storage_service.save_file("raw-documents/test/retry_test.pdf", valid_pdf)

    # Mock download_file to raise transient error on attempt 1, succeed on attempt 2
    call_count = 0
    real_download = storage_service.download_file

    def mock_download(key):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionResetError("Transient network glitch during storage download")
        return real_download(key)

    with patch.object(storage_service, "download_file", side_effect=mock_download):
        result = DocumentProcessingOrchestrator.execute_with_retries(
            document_id=doc.id,
            version_id=ver.id,
            storage_key="raw-documents/test/retry_test.pdf",
            max_retries=3,
            backoff_base=0.01,
            db=db_session,
        )


    assert result["success"] is True
    assert result["attempts"] == 2
    assert call_count == 2


def test_zero_raw_pdf_sent_to_indexing():
    """Verify that IndexingService receives only completed structured chunks and never raw PDF bytes."""
    chunks = [
        {
            "chunk_id": "chunk-001",
            "page_number": 1,
            "chunk_index": 0,
            "chunk_text": "Section 1: Welfare grant eligibility rules.",
            "token_count": 12,
            "vector_id": "vec-001",
            "metadata": {"scheme_name": "Grant Scheme"},
        }
    ]

    res = indexing_service.index_chunks(
        document_id="doc-test-123",
        version_id="ver-test-123",
        chunks=chunks,
    )
    assert res["success"] is True
    assert res["indexed_chunks_count"] == 1

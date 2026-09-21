"""
Tests for Semantic Document Chunking module.

Verifies:
1. Full traceability from every chunk back to DocumentPage, DocumentVersion, and Document.
2. Page number and page range preservation.
3. Section heading preservation and propagation across blocks.
4. Chunk size bounds and overlap behavior.
5. Preservation of tables and key-value blocks with headers.
6. Exact verbatim text for citations vs normalized text for search.
7. Scheme, department, location, language, effective date, and active version metadata attachment.
8. Exclusion of empty or meaningless chunks.
9. End-to-end database persistence and background job execution.
"""

import io
from datetime import datetime
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.app.db.migrator import DatabaseMigrator
from backend.app.db.session import SessionLocal
from backend.app.models.db_models import (
    Department,
    Document,
    DocumentCollection,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    User,
)
from backend.app.services.storage_service import storage_service
from backend.app.workers.background_jobs import DocumentProcessingOrchestrator
from backend.app.workers.chunker import SemanticChunk, SemanticChunker
from backend.app.workers.document_processor import DocumentProcessor


def generate_structured_welfare_pdf() -> bytes:
    """Generate a structured multi-page PDF with headings, paragraphs, and tables."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    # Page 1: Overview and Eligibility
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "PM KISAN WELFARE SCHEME 2026")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 720, "1. Scheme Overview")
    c.setFont("Helvetica", 10)
    c.drawString(50, 700, "The Pradhan Mantri Kisan Samman Nidhi provides income support to all landholding farmers' families.")
    c.drawString(50, 685, "Under the Scheme, the financial benefit of Rs. 6000 per year is transferred in three equal installments.")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 650, "2. Eligibility Criteria")
    c.setFont("Helvetica", 10)
    c.drawString(50, 630, "All landholding farmers families having cultivable landholding in their names are eligible.")
    c.drawString(50, 615, "Criteria Details:")
    c.drawString(60, 600, "| Category | Eligibility Status | Subsidy Amount |")
    c.drawString(60, 585, "| Small & Marginal Farmers | Eligible | Rs 6000/yr |")
    c.drawString(60, 570, "| Institutional Landholders | Ineligible | Rs 0 |")
    c.showPage()

    # Page 2: Application Process & Required Documents
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "3. Application Process")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Farmers can apply online through the official welfare portal or visit their local Common Service Centre.")
    c.drawString(50, 715, "Ensure all biometric credentials and Aadhaar linkages are updated before submitting.")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 680, "4. Documents Required")
    c.setFont("Helvetica", 10)
    c.drawString(50, 660, "Document-1: Aadhaar Card issued by UIDAI")
    c.drawString(50, 645, "Document-2: Land Ownership Certificate from Revenue Department")
    c.drawString(50, 630, "Document-3: Active Bank Account linked with Aadhaar")
    c.showPage()

    c.save()
    return buf.getvalue()


class TestSemanticChunkerUnit:
    """Unit tests for the SemanticChunker algorithm."""

    def test_heading_detection(self):
        """Test heading pattern detection for diverse formats."""
        assert SemanticChunker.is_heading("1. Scheme Overview") is True
        assert SemanticChunker.is_heading("SECTION 4: BENEFITS") is True
        assert SemanticChunker.is_heading("## Eligibility Criteria") is True
        assert SemanticChunker.is_heading("ELIGIBILITY CRITERIA") is True
        assert SemanticChunker.is_heading("Documents Required:") is True
        assert SemanticChunker.is_heading("This is a standard body paragraph that should not be a heading.") is False

    def test_text_normalization_for_search(self):
        """Test search text normalization: lowercasing, unicode NFKC, punctuation standardization."""
        raw_text = "SECTION 1: Farmers' Financial Aid (2026)—100% Direct-Benefit-Transfer! Special chars: @#$%^&*"
        normalized = SemanticChunker.normalize_text_for_search(raw_text)

        # Expected: lowercased, clean spacing, stripped extreme symbols but kept alphanumeric & essential punctuation
        assert "section 1:" in normalized
        assert "farmers" in normalized
        assert "financial aid" in normalized
        assert "100%" in normalized
        assert "direct-benefit-transfer" in normalized
        assert "@" not in normalized
        assert "#" not in normalized
        assert "$" not in normalized
        assert normalized == normalized.lower()

    def test_meaningful_and_noise_filtering(self):
        """Test exclusion of empty and meaningless chunks."""
        assert SemanticChunker.is_meaningful("Valid chunk containing enough meaningful words for processing.") is True
        assert SemanticChunker.is_meaningful("Too short") is False
        assert SemanticChunker.is_meaningful("   ") is False
        assert SemanticChunker.is_meaningful("--- ... !!! @@@ ###") is False
        assert SemanticChunker.is_meaningful("1 2 3") is False

    def test_table_block_preservation(self):
        """Test that table rows are kept together with their header lines."""
        table_text = (
            "ELIGIBILITY CRITERIA\n"
            "Below is the official table of categories:\n"
            "| Category | Income Limit | Assistance |\n"
            "| Marginal Farmers | Rs 100,000 | Rs 6,000 |\n"
            "| Small Farmers | Rs 200,000 | Rs 6,000 |\n"
            "| Large Farmers | None | Ineligible |\n\n"
            "Additional notes for applicants apply."
        )
        chunks = SemanticChunker.chunk_page(
            page_number=1,
            text=table_text,
            max_words=200,
        )

        assert len(chunks) >= 1
        first_chunk = chunks[0]
        # Verbatim text contains the table rows intact
        assert "| Category | Income Limit | Assistance |" in first_chunk.chunk_text
        assert "| Marginal Farmers | Rs 100,000 | Rs 6,000 |" in first_chunk.chunk_text
        assert "| Small Farmers | Rs 200,000 | Rs 6,000 |" in first_chunk.chunk_text

    def test_section_heading_propagation(self):
        """Test that chunks under a section inherit that section's heading."""
        text = (
            "SECTION 1: APPLICANT ELIGIBILITY\n\n"
            "All residents who have lived in the district for more than 5 years are eligible.\n\n"
            "Applicants must be at least 18 years of age and hold valid identification.\n\n"
            "SECTION 2: DISBURSEMENT SCHEDULE\n\n"
            "Payments are disbursed on the 1st of every calendar quarter directly into bank accounts."
        )
        chunks = SemanticChunker.chunk_page(
            page_number=1,
            text=text,
            max_words=15,  # Force multiple small chunks
            overlap_words=0,
        )

        assert len(chunks) >= 2
        # Section 1 heading attached to earlier chunks
        assert chunks[0].section_heading is not None
        assert "SECTION 1" in chunks[0].section_heading
        # Section 2 heading attached to later chunk
        assert any("SECTION 2" in (c.section_heading or "") for c in chunks)

    def test_chunk_size_and_overlap(self):
        """Test that chunks stay within word bounds and maintain sliding window overlap."""
        long_paragraph = " ".join([f"word{i}" for i in range(100)])
        chunks = SemanticChunker.chunk_page(
            page_number=1,
            text=long_paragraph,
            max_words=30,
            overlap_words=5,
        )

        assert len(chunks) >= 3
        for chunk in chunks:
            assert chunk.word_count <= 40  # Within reasonable bounds
            assert chunk.token_count > 0

        # Verify overlap exists between chunk 0 and chunk 1
        words_chunk0 = set(chunks[0].chunk_text.split())
        words_chunk1 = set(chunks[1].chunk_text.split())
        overlap = words_chunk0.intersection(words_chunk1)
        assert len(overlap) >= 3  # Contains overlapping words

    def test_metadata_attachment(self):
        """Test that metadata is populated on every chunk."""
        meta_ctx = {
            "scheme_name": "PM Kisan Samman Nidhi",
            "department": "Department of Agriculture",
            "state_or_district": "National",
            "language": "English",
            "effective_date": "2026-01-01",
            "active_version": 2,
            "is_active_version": True,
        }
        chunks = SemanticChunker.chunk_page(
            page_number=3,
            text="PM Kisan Samman Nidhi provides financial assistance directly to farmer bank accounts every four months.",
            page_range="3-4",
            metadata_context=meta_ctx,
        )

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.page_number == 3
        assert chunk.page_range == "3-4"
        assert chunk.metadata["scheme_name"] == "PM Kisan Samman Nidhi"
        assert chunk.metadata["department"] == "Department of Agriculture"
        assert chunk.metadata["state_or_district"] == "National"
        assert chunk.metadata["language"] == "English"
        assert chunk.metadata["active_version"] == 2
        assert chunk.metadata["is_active_version"] is True


class TestChunkingTraceabilityAndPipeline:
    """End-to-end tests proving database traceability and background processing."""

    def test_chunk_page_traceability_in_database(self):
        """
        Prove that every chunk persisted in the database can be traced back
        to its parent DocumentPage, DocumentVersion, and Document.
        """
        DatabaseMigrator.apply_migrations()
        db = SessionLocal()
        try:
            # 1. Setup sample hierarchy
            user = db.query(User).filter(User.email == "chunk_test_admin@welfare.gov.in").first()
            if not user:
                user = User(
                    email="chunk_test_admin@welfare.gov.in",
                    password_hash="hash",
                    full_name="Chunk Admin",
                    role="SYSTEM_ADMIN",
                )
                db.add(user)
                db.commit()

            dept = db.query(Department).first()
            if not dept:
                dept = Department(name="Ministry of Rural Development", code="MRD")
                db.add(dept)
                db.commit()

            ts = int(datetime.utcnow().timestamp())
            coll = DocumentCollection(
                name=f"Traceability Test Coll {ts}",
                slug=f"traceability-coll-{ts}",
                description="Test collection for chunk traceability",
                department_id=dept.id,
            )
            db.add(coll)
            db.commit()

            pdf_bytes = generate_structured_welfare_pdf()
            file_hash = DocumentProcessor.calculate_sha256(pdf_bytes)

            doc = Document(
                collection_id=coll.id,
                scheme_name="PM Awas Yojana Gramin",
                department="Ministry of Rural Development",
                state_or_district="All India",
                language="en",
                original_filename="pm_awas_yojana.pdf",
                storage_file_key="pending",
                file_hash=file_hash,
                version_number=1,
            )
            db.add(doc)
            db.commit()

            storage_key = f"documents/{doc.id}/v1/pm_awas_yojana.pdf"
            storage_service.save_file(
                storage_key=storage_key,
                content=pdf_bytes,
            )
            doc.storage_file_key = storage_key
            db.commit()

            ver = DocumentVersion(
                document_id=doc.id,
                version_number=1,
                original_filename="pm_awas_yojana.pdf",
                storage_file_key=storage_key,
                file_hash=file_hash,
                file_size_bytes=len(pdf_bytes),
                status=DocumentStatus.PROCESSING.value,
            )
            db.add(ver)
            db.commit()

            # 2. Run background processing pipeline
            res = DocumentProcessingOrchestrator.execute_with_retries(
                document_id=doc.id,
                version_id=ver.id,
                storage_key=storage_key,
            )
            assert res["success"] is True

            # 3. Verify chunks in database
            chunks = db.query(ExtractedChunk).filter(ExtractedChunk.version_id == ver.id).all()
            assert len(chunks) > 0

            # 4. Rigorous traceability assertion: every chunk points to valid Page, Version, Doc
            for chunk in chunks:
                # Direct foreign keys
                assert chunk.document_id == doc.id
                assert chunk.version_id == ver.id
                assert chunk.page_id is not None
                assert chunk.page_number >= 1
                assert chunk.page_range is not None

                # Exact text and normalized text
                assert len(chunk.chunk_text.strip()) > 0
                assert chunk.normalized_text is not None
                assert chunk.normalized_text == chunk.normalized_text.lower()

                # Relationship navigation
                parent_page = chunk.page
                assert parent_page is not None
                assert parent_page.id == chunk.page_id
                assert parent_page.page_number == chunk.page_number
                assert parent_page.version_id == ver.id

                parent_version = chunk.version
                assert parent_version is not None
                assert parent_version.id == ver.id

                # Metadata verification
                assert chunk.metadata_json is not None
                assert chunk.metadata_json["scheme_name"] == "PM Awas Yojana Gramin"
                assert chunk.metadata_json["department"] == "Ministry of Rural Development"
                assert chunk.metadata_json["page_number"] == chunk.page_number

        finally:
            db.close()

    def test_exact_verbatim_text_preserved_for_citations(self):
        """
        Verify that chunk_text preserves exact case, line formatting, and numbers
        needed for user-facing citation snippets.
        """
        raw_text = "Under the PM-KISAN Scheme, financial assistance of Rs. 6,000/- per year is credited."
        chunks = SemanticChunker.chunk_page(
            page_number=1,
            text=raw_text,
        )

        assert len(chunks) == 1
        chunk = chunks[0]
        # Exact verbatim text
        assert "Rs. 6,000/-" in chunk.chunk_text
        assert "PM-KISAN" in chunk.chunk_text
        # Normalized text for search
        assert "rs. 6 000" in chunk.normalized_text or "6,000" in chunk.normalized_text or "6000" in chunk.normalized_text
        assert "pm-kisan" in chunk.normalized_text

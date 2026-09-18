"""
Unit & Integration tests for all 14 database schema entities and document constraints.
"""

from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from backend.app.models.db_models import (
    AuditEvent,
    Citation,
    Department,
    Document,
    DocumentCollection,
    DocumentMetadata,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    ProcessingJob,
    QuestionAnswer,
    Role,
    SearchSession,
    User,
    UserFeedback,
)
from backend.app.models.schemas import UserRole


def test_14_entities_exist_in_metadata():
    """Verify that all 14 requested domain entities are mapped in the ORM schema."""
    expected_tables = {
        "users",
        "roles",
        "document_collections",
        "documents",
        "document_versions",
        "document_pages",
        "extracted_chunks",
        "processing_jobs",
        "document_metadata",
        "search_sessions",
        "question_answers",
        "citations",
        "audit_events",
        "user_feedback",
    }
    from backend.app.models.db_models import Base

    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


def test_document_record_fields_and_states(db_session: Session):
    """
    Verify document records support:
    - Original filename, Stored file key, MIME type, File hash
    - Scheme name, Department, State or district, Language
    - Publication date, Effective date, Version number
    - ACTIVE, ARCHIVED, PROCESSING, FAILED, and DELETED states.
    """
    col = DocumentCollection(
        name="Test Scheme Collection",
        slug="test-scheme-collection",
        description="Testing scheme collection",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    # Test all document lifecycle states
    states = [
        DocumentStatus.ACTIVE,
        DocumentStatus.ARCHIVED,
        DocumentStatus.PROCESSING,
        DocumentStatus.FAILED,
        DocumentStatus.DELETED,
    ]

    for st in states:
        doc = Document(
            collection_id=col.id,
            scheme_name=f"Scheme in {st.value} state",
            department="Ministry of Social Justice and Empowerment",
            state_or_district="State of Maharashtra",
            language="en",
            publication_date=datetime(2024, 2, 1),
            effective_date=datetime(2024, 4, 1),
            original_filename="sample_guidelines.pdf",
            storage_file_key=f"storage/docs/{st.value.lower()}/guidelines.pdf",
            mime_type="application/pdf",
            file_hash="abcd1234ef567890abcdef1234567890abcdef1234567890abcdef1234567890",
            version_number=1,
            status=st.value,
        )
        db_session.add(doc)
        db_session.commit()

        # Query back and verify
        saved_doc = db_session.query(Document).filter(Document.id == doc.id).first()
        assert saved_doc is not None
        assert saved_doc.scheme_name == f"Scheme in {st.value} state"
        assert saved_doc.department == "Ministry of Social Justice and Empowerment"
        assert saved_doc.state_or_district == "State of Maharashtra"
        assert saved_doc.language == "en"
        assert saved_doc.original_filename == "sample_guidelines.pdf"
        assert saved_doc.storage_file_key == f"storage/docs/{st.value.lower()}/guidelines.pdf"
        assert saved_doc.mime_type == "application/pdf"
        assert saved_doc.file_hash == "abcd1234ef567890abcdef1234567890abcdef1234567890abcdef1234567890"
        assert saved_doc.version_number == 1
        assert saved_doc.status == st.value


def test_document_required_indexes(db_session: Session):
    """
    Verify indexes for collection_id, status, scheme_name, department, effective_date, and file_hash.
    """
    inspector = inspect(db_session.bind)
    indexes = inspector.get_indexes("documents")
    indexed_columns = set()
    for idx in indexes:
        for col_name in idx["column_names"]:
            indexed_columns.add(col_name)

    required_indexed_cols = {
        "collection_id",
        "status",
        "scheme_name",
        "department",
        "effective_date",
        "file_hash",
    }
    assert required_indexed_cols.issubset(indexed_columns), f"Missing index columns: {required_indexed_cols - indexed_columns}"


def test_seeded_admin_and_collection(db_session: Session):
    """Verify seed data creates development administrator and sample collection."""
    # 1. Dev Admin verification
    admin = db_session.query(User).filter(User.email == "admin.dev@welfareconnect.local").first()
    assert admin is not None
    assert admin.role == UserRole.SYSTEM_ADMIN.value
    assert admin.is_active is True

    # 2. Sample Collection verification
    sample_col = db_session.query(DocumentCollection).filter(DocumentCollection.slug == "housing-urban-affairs").first()
    assert sample_col is not None
    assert "PMAY" in sample_col.name
    assert sample_col.is_active is True

    # 3. Sample Document verification
    sample_doc = db_session.query(Document).filter(Document.collection_id == sample_col.id).first()
    assert sample_doc is not None
    assert sample_doc.original_filename == "PMAY-U-Operational-Guidelines-2024.pdf"
    assert sample_doc.mime_type == "application/pdf"
    assert sample_doc.status == DocumentStatus.ACTIVE.value


def test_end_to_end_entity_relationships(db_session: Session):
    """Verify relational integrity across Document -> Version -> Page -> Chunk -> Citation -> QuestionAnswer -> UserFeedback."""
    # 1. Collection & Document
    col = DocumentCollection(
        name="Agriculture Subsidies",
        slug=f"agri-subsidies-{uuid.uuid4().hex[:6]}",
        description="Farmer support",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    doc = Document(
        collection_id=col.id,
        scheme_name="Kisan Credit Card Scheme",
        department="Ministry of Agriculture",
        original_filename="KCC_Scheme_2024.pdf",
        storage_file_key="raw/kcc.pdf",
        mime_type="application/pdf",
        file_hash="hash1234567890hash1234567890hash1234567890hash1234567890hash12345678",
        status=DocumentStatus.ACTIVE.value,
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Version
    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename="KCC_Scheme_2024.pdf",
        storage_file_key="raw/kcc.pdf",
        mime_type="application/pdf",
        file_hash="hash1234567890hash1234567890hash1234567890hash1234567890hash12345678",
        total_pages=5,
        status=DocumentStatus.ACTIVE.value,
    )
    db_session.add(ver)
    db_session.commit()

    # 3. Page
    page = DocumentPage(
        version_id=ver.id,
        document_id=doc.id,
        page_number=3,
        raw_text="Eligible farmers can get credit limit up to Rs. 3,00,000 at concessional interest rate of 4%.",
        word_count=18,
    )
    db_session.add(page)
    db_session.commit()

    # 4. Extracted Chunk
    chunk = ExtractedChunk(
        page_id=page.id,
        version_id=ver.id,
        document_id=doc.id,
        chunk_index=0,
        chunk_text="Eligible farmers can get credit limit up to Rs. 3,00,000 at concessional interest rate of 4%.",
        token_count=18,
        start_char_offset=0,
        end_char_offset=95,
        vector_id="vec-kcc-001",
    )
    db_session.add(chunk)
    db_session.commit()

    # 5. Search Session & Question Answer
    session_rec = SearchSession(
        session_token=f"sess-{uuid.uuid4()}",
        collection_id=col.id,
    )
    db_session.add(session_rec)
    db_session.commit()

    qa = QuestionAnswer(
        session_id=session_rec.id,
        collection_id=col.id,
        question="What is the credit limit for Kisan Credit Card?",
        answer="Credit limit is up to Rs. 3,00,000 at 4% interest rate.",
        is_refusal=False,
        latency_ms=150,
    )
    db_session.add(qa)
    db_session.commit()

    # 6. Citation
    citation = Citation(
        qa_id=qa.id,
        document_id=doc.id,
        chunk_id=chunk.id,
        page_number=3,
        document_title="Kisan Credit Card Scheme",
        excerpt="Eligible farmers can get credit limit up to Rs. 3,00,000",
        confidence_score=0.98,
    )
    db_session.add(citation)
    db_session.commit()

    # 7. User Feedback
    feedback = UserFeedback(
        qa_id=qa.id,
        rating=1,
        feedback_text="Very accurate citation from official circular.",
    )
    db_session.add(feedback)
    db_session.commit()

    # 8. Processing Job & Metadata
    job = ProcessingJob(
        document_id=doc.id,
        version_id=ver.id,
        job_type="PDF_INGESTION",
        status="COMPLETED",
        progress_percent=100,
    )
    meta = DocumentMetadata(
        document_id=doc.id,
        version_id=ver.id,
        meta_key="interest_rate",
        meta_value="4%",
        data_type="string",
    )
    db_session.add(job)
    db_session.add(meta)
    db_session.commit()

    # Verify relationships navigate properly
    retrieved_qa = db_session.query(QuestionAnswer).filter(QuestionAnswer.id == qa.id).first()
    assert len(retrieved_qa.citations) == 1
    assert retrieved_qa.citations[0].page_number == 3
    assert len(retrieved_qa.feedbacks) == 1
    assert retrieved_qa.feedbacks[0].rating == 1

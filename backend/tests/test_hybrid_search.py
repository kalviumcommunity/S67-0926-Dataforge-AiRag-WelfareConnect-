"""
Tests for FastAPI Hybrid Search Service.

Verifies:
1. Exact matching (identifiers, names, numbers, phrases).
2. Semantic matching (Pinecone vector retrieval via embeddings).
3. Metadata filtering (scheme, department, location, language).
4. Collection isolation (queries isolated to specific collection).
5. Active-only preference and historical search access control.
6. Score threshold filtering and zero-hallucination refusal.
7. Preserved metadata and detailed retrieval reasons.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.security import create_access_token
from backend.app.db.migrator import DatabaseMigrator
from backend.app.db.session import SessionLocal
from backend.app.main import app
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
from backend.app.models.schemas import QueryRequest, UserRole
from backend.app.services.indexing_service import indexing_service
from backend.app.services.pinecone_service import pinecone_service
from backend.app.services.search_service import search_service


@pytest.fixture(autouse=True)
def setup_database_and_migrations():
    """Ensure all migrations and latest columns are applied."""
    DatabaseMigrator.apply_migrations()


@pytest.fixture
def db_session():
    """Yield a database session and clean up afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def citizen_auth_headers(db_session: Session):
    """Generate JWT auth headers for a standard citizen account."""
    citizen = db_session.query(User).filter(User.role == "CITIZEN").first()
    if not citizen:
        citizen = User(
            email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hash",
            full_name="Test Citizen",
            role="CITIZEN",
        )
        db_session.add(citizen)
        db_session.commit()

    token = create_access_token(
        user_id=citizen.id,
        email=citizen.email,
        role=UserRole.CITIZEN,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(db_session: Session):
    """Generate JWT auth headers for an administrator account."""
    admin = db_session.query(User).filter(User.role == "SYSTEM_ADMIN").first()
    if not admin:
        admin = User(
            email=f"search_admin_{uuid.uuid4().hex[:6]}@welfare.gov.in",
            password_hash="hash",
            full_name="Search Admin",
            role="SYSTEM_ADMIN",
        )
        db_session.add(admin)
        db_session.commit()

    token = create_access_token(
        user_id=admin.id,
        email=admin.email,
        role=UserRole.SYSTEM_ADMIN,
    )
    return {"Authorization": f"Bearer {token}"}


def create_indexed_scheme(
    db: Session,
    collection_id: Optional[str] = None,
    scheme_name: str = "PM-Kisan Income Support",
    department: str = "Ministry of Agriculture",
    state_or_district: str = "National",
    language: str = "en",
    status: str = DocumentStatus.ACTIVE.value,
    custom_text: str = "PM-KISAN provides direct income transfer of Rs. 6000 per year in three installments to farmer households.",
    page_number: int = 1,
    section_heading: str = "1. Financial Assistance",
):
    """Helper to create and index a welfare document with ExtractedChunks into both DB and Pinecone."""
    uid = uuid.uuid4().hex[:8]

    if not collection_id:
        dept_rec = db.query(Department).first()
        if not dept_rec:
            dept_rec = Department(name="Ministry of Agriculture", code="MOA")
            db.add(dept_rec)
            db.commit()

        coll = DocumentCollection(
            name=f"Collection {uid}",
            slug=f"coll-{uid}",
            description="Test collection",
            department_id=dept_rec.id,
        )
        db.add(coll)
        db.commit()
        collection_id = coll.id

    doc = Document(
        collection_id=collection_id,
        scheme_name=scheme_name,
        department=department,
        state_or_district=state_or_district,
        language=language,
        original_filename=f"{uid}.pdf",
        storage_file_key=f"docs/{uid}.pdf",
        file_hash=f"hash-{uid}",
        version_number=1,
        status=status,
        effective_date=datetime(2026, 1, 1),
    )
    db.add(doc)
    db.commit()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename=f"{uid}.pdf",
        storage_file_key=f"docs/{uid}.pdf",
        file_hash=f"hash-{uid}",
        file_size_bytes=4000,
        status=status,
        effective_date=datetime(2026, 1, 1),
    )
    db.add(ver)
    db.commit()

    page = DocumentPage(
        version_id=ver.id,
        document_id=doc.id,
        page_number=page_number,
        raw_text=custom_text,
        native_text=custom_text,
        word_count=len(custom_text.split()),
    )
    db.add(page)
    db.commit()

    chunk = ExtractedChunk(
        page_id=page.id,
        version_id=ver.id,
        document_id=doc.id,
        chunk_index=0,
        page_number=page_number,
        page_range=str(page_number),
        section_heading=section_heading,
        chunk_text=custom_text,
        normalized_text=custom_text.lower(),
        token_count=len(custom_text.split()),
        vector_id=f"{ver.id}:{page_number}:0",
    )
    db.add(chunk)
    db.commit()

    # Index into Pinecone (and in-memory store)
    indexing_service.upsert_document_version_vectors(db=db, version_id=ver.id)

    return collection_id, doc, ver, chunk


class TestFastAPIHybridSearch:
    """Test suite for the hybrid search service."""

    def test_exact_keyword_matching(self, db_session: Session):
        """Verify exact identifier and term matching (e.g. 'PM-KISAN')."""
        coll_id, doc, ver, chunk = create_indexed_scheme(
            db_session,
            scheme_name="PM-KISAN Samman Nidhi",
            custom_text="PM-KISAN circular provides official income benefits for agrarian households.",
        )

        req = QueryRequest(
            query="PM-KISAN",
            collection_id=coll_id,
        )
        citations = search_service.hybrid_search(db_session, req)

        assert len(citations) > 0
        first_cit = citations[0]
        assert first_cit.document_id == doc.id
        assert "PM-KISAN" in first_cit.excerpt
        assert "Keyword Match" in (first_cit.retrieval_reason or "") or "Hybrid Match" in (first_cit.retrieval_reason or "")
        assert first_cit.score >= settings.SEARCH_SIMILARITY_THRESHOLD

    def test_semantic_vector_matching(self, db_session: Session):
        """Verify semantic similarity retrieval when query rephrases the content."""
        coll_id, doc, ver, chunk = create_indexed_scheme(
            db_session,
            scheme_name="Pradhan Mantri Matru Vandana Yojana",
            custom_text="Financial compensation of five thousand rupees is granted for pregnant women and lactating mothers for health nutrition.",
        )

        req = QueryRequest(
            query="cash assistance for pregnant women maternal nutrition",
            collection_id=coll_id,
        )
        citations = search_service.hybrid_search(db_session, req)

        assert len(citations) > 0
        first_cit = citations[0]
        assert first_cit.document_id == doc.id
        assert first_cit.score >= settings.SEARCH_SIMILARITY_THRESHOLD
        assert first_cit.retrieval_reason is not None

    def test_metadata_filtering(self, db_session: Session):
        """Verify filtering by department, language, and scheme."""
        coll_id, doc_agri, _, _ = create_indexed_scheme(
            db_session,
            scheme_name="National Agriculture Support",
            department="Department of Agriculture",
            language="en",
            custom_text="Subsidies for seed cultivation and farm tools.",
        )
        _, doc_health, _, _ = create_indexed_scheme(
            db_session,
            collection_id=coll_id,
            scheme_name="National Health Mission",
            department="Ministry of Health",
            language="hi",
            custom_text="Primary healthcare centers and maternal checkups.",
        )

        # 1. Filter by Department
        req_dept = QueryRequest(
            query="subsidies healthcare",
            collection_id=coll_id,
            department="Agriculture",
        )
        res_dept = search_service.hybrid_search(db_session, req_dept)
        assert len(res_dept) > 0
        assert all("Agriculture" in c.department for c in res_dept)

        # 2. Filter by Language
        req_lang = QueryRequest(
            query="healthcare checkups",
            collection_id=coll_id,
            language="hi",
        )
        res_lang = search_service.hybrid_search(db_session, req_lang)
        assert len(res_lang) > 0
        assert all(c.language == "hi" for c in res_lang)

    def test_collection_isolation(self, db_session: Session):
        """Verify that a query for Collection A never retrieves documents from Collection B."""
        coll_a, doc_a, _, _ = create_indexed_scheme(
            db_session,
            scheme_name="Scheme Collection Alpha",
            custom_text="Confidential guidelines exclusively in Collection Alpha for local district administration.",
        )
        coll_b, doc_b, _, _ = create_indexed_scheme(
            db_session,
            scheme_name="Scheme Collection Beta",
            custom_text="Confidential guidelines exclusively in Collection Beta for public distribution.",
        )

        # Query Collection A
        req_a = QueryRequest(
            query="Confidential guidelines",
            collection_id=coll_a,
        )
        res_a = search_service.hybrid_search(db_session, req_a)

        assert len(res_a) > 0
        assert all(c.document_id == doc_a.id for c in res_a)
        assert not any(c.document_id == doc_b.id for c in res_a)

    def test_active_only_and_historical_access_control(self, db_session: Session, citizen_auth_headers, admin_auth_headers):
        """Verify that active documents are returned by default, and historical search requires admin privileges."""
        client = TestClient(app)
        coll_id, doc_arch, ver_arch, _ = create_indexed_scheme(
            db_session,
            scheme_name="Archived Historical Policy 2018",
            status=DocumentStatus.ARCHIVED.value,
            custom_text="Historical pension rates for senior citizens superseded by 2026 regulations.",
        )

        # Citizen attempting historical search -> 403 Forbidden
        res_citizen = client.post(
            "/api/v1/query/search",
            headers=citizen_auth_headers,
            json={
                "query": "Historical pension rates",
                "collection_id": coll_id,
                "include_historical": True,
            },
        )
        assert res_citizen.status_code == 403

        # Default query (active only) -> Returns refusal or 0 citations for archived doc
        res_default = client.post(
            "/api/v1/query/search",
            headers=citizen_auth_headers,
            json={
                "query": "Historical pension rates",
                "collection_id": coll_id,
                "include_historical": False,
            },
        )
        assert res_default.status_code == 200
        assert res_default.json()["is_refusal"] is True or len(res_default.json()["citations"]) == 0

        # Admin with historical permission enabled -> successfully searches archived
        res_admin = client.post(
            "/api/v1/query/search",
            headers=admin_auth_headers,
            json={
                "query": "Historical pension rates",
                "collection_id": coll_id,
                "include_historical": True,
            },
        )
        assert res_admin.status_code == 200
        data_admin = res_admin.json()
        assert len(data_admin["citations"]) > 0
        assert data_admin["citations"][0]["is_historical"] is True

    def test_similarity_threshold_filtering_and_refusal(self, db_session: Session):
        """Verify that low-relevance out-of-domain queries return refusal and zero citations."""
        coll_id, doc, _, _ = create_indexed_scheme(
            db_session,
            scheme_name="PMAY Housing Assistance",
            custom_text="Financial subsidy for rural pakka house construction under Pradhan Mantri Awas Yojana.",
        )

        # Unrelated query that should not match housing assistance
        req_unrelated = QueryRequest(
            query="astronomy astrophysics black hole event horizon quantum physics",
            collection_id=coll_id,
        )
        res = search_service.execute_query(db_session, req_unrelated)

        assert res.is_refusal is True
        assert len(res.citations) == 0
        assert "not found in the uploaded official scheme documents" in res.answer.lower()

    def test_preserved_metadata_and_retrieval_reasons(self, db_session: Session):
        """Verify that every citation contains complete metadata and retrieval reason."""
        coll_id, doc, ver, chunk = create_indexed_scheme(
            db_session,
            scheme_name="Ayushman Bharat PM-JAY",
            department="National Health Authority",
            state_or_district="National",
            language="en",
            page_number=7,
            section_heading="Clause 4: Secondary & Tertiary Care",
            custom_text="Ayushman Bharat PM-JAY provides health cover up to 5 lakh rupees per family per year for secondary care hospitalization.",
        )

        req = QueryRequest(
            query="Ayushman Bharat 5 lakh health cover",
            collection_id=coll_id,
        )
        res = search_service.execute_query(db_session, req)

        assert res.is_refusal is False
        assert len(res.citations) > 0
        cit = res.citations[0]

        assert cit.document_id == doc.id
        assert cit.page_number == 7
        assert cit.section_heading == "Clause 4: Secondary & Tertiary Care"
        assert cit.department == "National Health Authority"
        assert cit.language == "en"
        assert cit.retrieval_reason is not None
        assert "Match" in cit.retrieval_reason
        assert cit.score >= settings.SEARCH_SIMILARITY_THRESHOLD

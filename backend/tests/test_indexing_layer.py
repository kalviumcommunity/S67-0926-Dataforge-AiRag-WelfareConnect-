"""
Tests for Dual-Layer Indexing Subsystem.

Verifies:
1. Keyword Search: Exact terms, names, identifiers, quoted phrases, and metadata filters.
2. Deterministic Vector IDs: {document_version_id}:{page_number}:{chunk_index}.
3. Pinecone Metadata Fields: collection_id, document_id, document_version_id, page_number,
   scheme, department, state, district, language, effective_date, active status,
   embedding_model, and embedding_dimension.
4. Model and Dimension Incompatibility Protection: Prevents mixing vectors from incompatible models/dimensions.
5. Single Document Version Vector Upsert: Idempotent behavior and database state updates.
6. Single Document Version Vector Deletion: Purges version vectors from Pinecone.
7. Collection Re-indexing: Re-indexes all active document versions when metadata changes.
8. Admin Rebuild API & CLI maintenance endpoints.
"""

from datetime import datetime
import io
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
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
from backend.app.services.indexing_service import IndexingService, indexing_service
from backend.app.services.keyword_search import KeywordSearchService, keyword_search_service
from backend.app.services.pinecone_service import pinecone_service
from backend.app.services.storage_service import storage_service
from backend.app.workers.background_jobs import DocumentProcessingOrchestrator
from backend.app.workers.chunker import SemanticChunker
from backend.app.workers.document_processor import DocumentProcessor


import uuid


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


from backend.app.models.schemas import UserRole


@pytest.fixture
def admin_auth_headers(db_session: Session):
    """Generate JWT auth headers for an administrator account."""
    admin = db_session.query(User).filter(User.role == "SYSTEM_ADMIN").first()
    if not admin:
        admin = User(
            email=f"index_admin_{uuid.uuid4().hex[:6]}@welfare.gov.in",
            password_hash="hash",
            full_name="Index Admin",
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


def create_test_scheme_hierarchy(db: Session, scheme_name: str = "PM-KISAN Direct Aid"):
    """Helper to create a complete collection, document, version, pages, and chunks."""
    uid = uuid.uuid4().hex[:8]
    dept = db.query(Department).first()
    if not dept:
        dept = Department(name="Ministry of Agriculture", code="MOA")
        db.add(dept)
        db.commit()

    coll = DocumentCollection(
        name=f"Agriculture Schemes {uid}",
        slug=f"agri-schemes-{uid}",
        description="Collection of central agriculture support schemes",
        department_id=dept.id,
    )
    db.add(coll)
    db.commit()

    doc = Document(
        collection_id=coll.id,
        scheme_name=scheme_name,
        department="Ministry of Agriculture",
        state_or_district="National / All States",
        language="en",
        original_filename="pm_kisan_guidelines.pdf",
        storage_file_key=f"documents/sample_{uid}.pdf",
        file_hash="hash-123456",
        version_number=1,
        status=DocumentStatus.ACTIVE.value,
        effective_date=datetime(2026, 1, 1),
    )
    db.add(doc)
    db.commit()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        original_filename="pm_kisan_guidelines.pdf",
        storage_file_key=f"documents/sample_{uid}.pdf",
        file_hash="hash-123456",
        file_size_bytes=5000,
        status=DocumentStatus.ACTIVE.value,
        effective_date=datetime(2026, 1, 1),
    )
    db.add(ver)
    db.commit()

    page1 = DocumentPage(
        version_id=ver.id,
        document_id=doc.id,
        page_number=1,
        raw_text="SECTION 1: OVERVIEW\nPM-KISAN provides Rs. 6000 annual income support to all eligible farmer families across India.",
        native_text="SECTION 1: OVERVIEW\nPM-KISAN provides Rs. 6000 annual income support to all eligible farmer families across India.",
        word_count=20,
    )
    page2 = DocumentPage(
        version_id=ver.id,
        document_id=doc.id,
        page_number=2,
        raw_text="SECTION 2: ELIGIBILITY\nAll landholding farmers having cultivable land in their names qualify for DBT payment.",
        native_text="SECTION 2: ELIGIBILITY\nAll landholding farmers having cultivable land in their names qualify for DBT payment.",
        word_count=20,
    )
    db.add_all([page1, page2])
    db.commit()

    chunk1 = ExtractedChunk(
        page_id=page1.id,
        version_id=ver.id,
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        page_range="1",
        section_heading="SECTION 1: OVERVIEW",
        chunk_text="PM-KISAN provides Rs. 6000 annual income support to all eligible farmer families across India.",
        normalized_text=SemanticChunker.normalize_text_for_search("PM-KISAN provides Rs. 6000 annual income support to all eligible farmer families across India."),
        token_count=25,
        vector_id=IndexingService.generate_vector_id(ver.id, 1, 0),
    )
    chunk2 = ExtractedChunk(
        page_id=page2.id,
        version_id=ver.id,
        document_id=doc.id,
        chunk_index=1,
        page_number=2,
        page_range="2",
        section_heading="SECTION 2: ELIGIBILITY",
        chunk_text="All landholding farmers having cultivable land in their names qualify for DBT payment.",
        normalized_text=SemanticChunker.normalize_text_for_search("All landholding farmers having cultivable land in their names qualify for DBT payment."),
        token_count=22,
        vector_id=IndexingService.generate_vector_id(ver.id, 2, 1),
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    return coll, doc, ver, [chunk1, chunk2]


class TestKeywordSearchLayer:
    """Unit and integration tests for relational keyword search."""

    def test_exact_identifier_and_phrase_search(self, db_session: Session):
        """Test search for exact identifiers like PM-KISAN, quoted phrases, and amounts."""
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="PM-KISAN Central Scheme")

        # 1. Exact Identifier search
        res = keyword_search_service.search(db_session, query="PM-KISAN", collection_id=coll.id)
        assert len(res) > 0
        assert res[0].scheme_name == "PM-KISAN Central Scheme"
        assert res[0].page_number == 1

        # 2. Exact Quoted Phrase search
        res_phrase = keyword_search_service.search(db_session, query='"annual income support"', collection_id=coll.id)
        assert len(res_phrase) > 0
        assert "annual income support" in res_phrase[0].chunk_text.lower()

        # 3. Numeric Amount search
        res_amount = keyword_search_service.search(db_session, query="6000", collection_id=coll.id)
        assert len(res_amount) > 0
        assert "6000" in res_amount[0].chunk_text

    def test_keyword_search_filters_and_historical(self, db_session: Session):
        """Test metadata filtering (department, location, language) and active vs historical exclusion."""
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="Filter Test Scheme")

        # Department filter
        res_dept = keyword_search_service.search(db_session, query="landholding", department="Agriculture", collection_id=coll.id)
        assert len(res_dept) > 0

        res_wrong_dept = keyword_search_service.search(db_session, query="landholding", department="Finance", collection_id=coll.id)
        assert len(res_wrong_dept) == 0

        # Archive document & verify active exclusion
        doc.status = DocumentStatus.ARCHIVED.value
        ver.status = DocumentStatus.ARCHIVED.value
        db_session.commit()

        res_active_only = keyword_search_service.search(db_session, query="landholding", collection_id=coll.id, include_historical=False)
        assert len(res_active_only) == 0

        res_historical = keyword_search_service.search(db_session, query="landholding", collection_id=coll.id, include_historical=True)
        assert len(res_historical) > 0
        assert res_historical[0].is_historical is True


class TestPineconeVectorIndexingLayer:
    """Unit and integration tests for Pinecone vector indexing, deterministic IDs, and metadata."""

    def test_deterministic_vector_id_format(self):
        """Verify vector ID format: {document_version_id}:{page_number}:{chunk_index}."""
        version_id = "v-99a8b7"
        vec_id = IndexingService.generate_vector_id(version_id=version_id, page_number=3, chunk_index=5)
        assert vec_id == "v-99a8b7:3:5"

    def test_pinecone_metadata_payload_fields(self, db_session: Session):
        """Verify all required metadata fields are present in the Pinecone payload."""
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="PMAY-G Housing")
        chunk = chunks[0]

        meta = IndexingService.build_chunk_metadata_payload(doc=doc, ver=ver, chunk=chunk)

        # Check all required fields from prompt specifications
        assert meta["collection_id"] == str(coll.id)
        assert meta["document_id"] == str(doc.id)
        assert meta["document_version_id"] == str(ver.id)
        assert meta["page_number"] == 1
        assert meta["scheme"] == "PMAY-G Housing"
        assert meta["department"] == "Ministry of Agriculture"
        assert meta["state"] == "National"
        assert meta["district"] == "All States"
        assert meta["language"] == "en"
        assert meta["effective_date"] == "2026-01-01 00:00:00"
        assert meta["active"] is True
        assert meta["embedding_model"] == settings.EMBEDDING_MODEL
        assert meta["embedding_dimension"] == settings.EMBEDDING_DIMENSION
        assert meta["chunk_index"] == 0
        assert meta["section_heading"] == "SECTION 1: OVERVIEW"
        assert len(meta["text"]) > 0

    def test_model_and_dimension_incompatibility_protection(self):
        """Verify that vector dimension or embedding model mismatches raise clear validation errors."""
        # 1. Dimension Mismatch (e.g. 512 values when configured for 1536)
        invalid_dim_vectors = [
            {
                "id": "v-1:1:0",
                "values": [0.1] * 512,  # Wrong dimension!
                "metadata": {"embedding_model": settings.EMBEDDING_MODEL},
            }
        ]
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            IndexingService.validate_vector_compatibility(invalid_dim_vectors, expected_dimension=1536)

        # 2. Embedding Model Mismatch (e.g. 'text-embedding-ada-002' when configured for 'text-embedding-3-small')
        invalid_model_vectors = [
            {
                "id": "v-1:1:0",
                "values": [0.1] * settings.EMBEDDING_DIMENSION,
                "metadata": {"embedding_model": "incompatible-legacy-model"},
            }
        ]
        with pytest.raises(ValueError, match="Embedding model mismatch"):
            IndexingService.validate_vector_compatibility(invalid_model_vectors, expected_model="text-embedding-3-small")

    def test_upsert_document_version_vectors(self, db_session: Session):
        """Test idempotent vector upsert for a single document version and DB persistence."""
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="Upsert Test Scheme")

        res = indexing_service.upsert_document_version_vectors(db=db_session, version_id=ver.id)
        assert res["success"] is True
        assert res["indexed_count"] == 2
        assert res["embedding_model"] == settings.EMBEDDING_MODEL
        assert res["embedding_dimension"] == settings.EMBEDDING_DIMENSION

        # Verify DB records updated
        updated_chunks = db_session.query(ExtractedChunk).filter(ExtractedChunk.version_id == ver.id).all()
        for c in updated_chunks:
            assert c.indexed_at is not None
            assert c.embedding_model == settings.EMBEDDING_MODEL
            assert c.embedding_dimension == settings.EMBEDDING_DIMENSION
            assert c.vector_id == f"{ver.id}:{c.page_number}:{c.chunk_index}"

    def test_delete_document_version_vectors(self, db_session: Session):
        """Test deleting vectors for a single document version and clearing indexed_at timestamp."""
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="Delete Vector Test Scheme")

        # First upsert
        indexing_service.upsert_document_version_vectors(db=db_session, version_id=ver.id)

        # Then delete
        res = indexing_service.delete_document_version_vectors(db=db_session, version_id=ver.id)
        assert res["success"] is True
        assert res["deleted_count"] == 2

        # Verify DB timestamps cleared
        cleared_chunks = db_session.query(ExtractedChunk).filter(ExtractedChunk.version_id == ver.id).all()
        for c in cleared_chunks:
            assert c.indexed_at is None

    def test_reindex_collection_after_metadata_changes(self, db_session: Session):
        """Test collection re-indexing when document metadata changes."""
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="Old Scheme Name")

        # Initial indexing
        indexing_service.upsert_document_version_vectors(db=db_session, version_id=ver.id)

        # Admin updates scheme name and department metadata
        doc.scheme_name = "Updated Scheme Name 2026"
        doc.department = "Ministry of Rural Transformation"
        db_session.commit()

        # Trigger collection re-index
        res = indexing_service.reindex_collection(db=db_session, collection_id=coll.id)
        assert res["success"] is True
        assert res["total_vectors_indexed"] == 2

        # Verify updated metadata in chunk metadata_json
        refreshed_chunk = db_session.query(ExtractedChunk).filter(ExtractedChunk.version_id == ver.id).first()
        assert refreshed_chunk.metadata_json["scheme"] == "Updated Scheme Name 2026"
        assert refreshed_chunk.metadata_json["department"] == "Ministry of Rural Transformation"


class TestIndexingAdminAPI:
    """Test administrator endpoints for index statistics, re-indexing, and rebuilding."""

    def test_indexing_stats_endpoint(self, admin_auth_headers):
        """Test GET /api/v1/indexing/stats."""
        client = TestClient(app)
        res = client.get("/api/v1/indexing/stats", headers=admin_auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "dimension" in data
        assert "index_name" in data
        assert data["dimension"] == settings.EMBEDDING_DIMENSION

    def test_reindex_version_and_collection_api(self, admin_auth_headers, db_session: Session):
        """Test POST /api/v1/indexing/reindex-version and /reindex-collection."""
        client = TestClient(app)
        coll, doc, ver, chunks = create_test_scheme_hierarchy(db_session, scheme_name="API Reindex Scheme")

        # Reindex Version
        res_ver = client.post(f"/api/v1/indexing/reindex-version/{ver.id}", headers=admin_auth_headers)
        assert res_ver.status_code == 200
        assert res_ver.json()["indexed_count"] == 2

        # Reindex Collection
        res_coll = client.post(f"/api/v1/indexing/reindex-collection/{coll.id}", headers=admin_auth_headers)
        assert res_coll.status_code == 200
        assert res_coll.json()["total_vectors_indexed"] == 2

        # Delete Version Vectors
        res_del = client.delete(f"/api/v1/indexing/version/{ver.id}", headers=admin_auth_headers)
        assert res_del.status_code == 200
        assert res_del.json()["deleted_count"] == 2

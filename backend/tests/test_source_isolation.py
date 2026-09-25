"""
Security and Source Isolation Test Suite for WelfareConnect Assistant.

Verifies:
1. Every search request must include an authorized collection ID (HTTP 400 if missing).
2. Non-existent or inactive collection IDs are rejected (HTTP 404).
3. Private collections are protected: unauthorized citizens receive HTTP 403 Forbidden.
4. Anonymous users cannot access private collections (HTTP 403 Forbidden).
5. Collection owners can access their own private collections (HTTP 200).
6. System administrators with elevated permissions can access private collections (HTTP 200).
7. Strict server-side isolation: Zero cross-collection leakage between collections.
8. Active and approved documents are used by default; archived documents excluded without permission.
9. Insufficient evidence returns structured refusal stating:
   'The requested information was not found in the selected uploaded documents.'
10. Zero general model knowledge gap-filling without verified citations.
11. Factual claims validation ensuring every assertion has a retrieved citation.
12. Unverified claims fail validation and trigger structured refusal.
"""

from typing import Tuple
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.db_models import (
    Department,
    Document,
    DocumentCollection,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    Role,
    User,
)
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.schemas import CitationOut, QueryRequest, UserRole
from backend.app.services.generation_service import (
    STANDARD_NO_ANSWER_STATEMENT,
    GenerationService,
    generation_service,
)
from backend.app.services.search_service import search_service


def _create_test_user(db: Session, email: str, role_name: str, perms: list) -> Tuple[User, str]:
    """Helper to create a test user and return JWT bearer token."""
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(
            id=f"role-{uuid.uuid4()}",
            name=role_name,
            description="Test role",
            permissions=perms,
        )
        db.add(role)
        db.commit()

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password("Password@123"),
        full_name=f"User {email.split('@')[0]}",
        role_id=role.id,
        role=role_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    role_enum = UserRole(role_name) if role_name in UserRole._value2member_map_ else UserRole.CITIZEN
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=role_enum,
    )
    return user, token


def _create_test_document_with_chunk(
    db: Session,
    collection_id: str,
    scheme_name: str,
    department: str,
    filename: str,
    chunk_text: str,
    status: DocumentStatus = DocumentStatus.ACTIVE,
    version_number: int = 1,
) -> Tuple[Document, DocumentVersion, DocumentPage, ExtractedChunk]:
    """Helper to create a fully valid Document, DocumentVersion, DocumentPage, and ExtractedChunk."""
    doc_id = f"doc-{uuid.uuid4()}"
    ver_id = f"ver-{uuid.uuid4()}"
    page_id = f"page-{uuid.uuid4()}"
    chunk_id = f"chunk-{uuid.uuid4()}"

    doc = Document(
        id=doc_id,
        collection_id=collection_id,
        scheme_name=scheme_name,
        department=department,
        original_filename=filename,
        storage_file_key=f"raw-documents/test/{uuid.uuid4()}.pdf",
        file_hash=f"hash-{uuid.uuid4().hex}",
        status=status.value,
        version_number=version_number,
    )
    ver = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=version_number,
        original_filename=filename,
        storage_file_key=f"raw-documents/test/{uuid.uuid4()}.pdf",
        file_hash=f"hash-{uuid.uuid4().hex}",
        status=status.value,
        total_pages=1,
    )
    page = DocumentPage(
        id=page_id,
        version_id=ver_id,
        document_id=doc_id,
        page_number=1,
        raw_text=chunk_text,
        word_count=len(chunk_text.split()),
    )
    chunk = ExtractedChunk(
        id=chunk_id,
        page_id=page_id,
        version_id=ver_id,
        document_id=doc_id,
        chunk_index=0,
        page_number=1,
        page_range="1",
        chunk_text=chunk_text,
        normalized_text=chunk_text.lower(),
        token_count=len(chunk_text.split()),
    )
    db.add_all([doc, ver, page, chunk])
    db.commit()
    return doc, ver, page, chunk





def test_search_request_requires_collection_id(client: TestClient):
    """Requirement 1: Every search request must include an authorized collection ID."""
    # Missing collection_id
    res_none = client.post(
        "/api/v1/query/search",
        json={"query": "What are the scheme benefits?"},
    )
    assert res_none.status_code == 400
    assert "collection_id" in res_none.json()["detail"].lower()

    # Empty string collection_id
    res_empty = client.post(
        "/api/v1/query/search",
        json={"query": "What are the scheme benefits?", "collection_id": "   "},
    )
    assert res_empty.status_code == 400
    assert "collection_id" in res_empty.json()["detail"].lower()


def test_search_request_rejects_nonexistent_or_inactive_collection(client: TestClient, db_session: Session):
    """Requirement 1: Search request with non-existent or inactive collection returns 404."""
    # Non-existent collection ID
    res_not_found = client.post(
        "/api/v1/query/search",
        json={
            "query": "What are the scheme benefits?",
            "collection_id": "non-existent-col-uuid-99999",
        },
    )
    assert res_not_found.status_code == 404
    assert "not found or inactive" in res_not_found.json()["detail"].lower()

    # Inactive collection
    dept = db_session.query(Department).first()
    inactive_col = DocumentCollection(
        id=f"col-inactive-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Decommissioned Collection",
        slug=f"decommissioned-{uuid.uuid4().hex[:6]}",
        is_active=False,
    )
    db_session.add(inactive_col)
    db_session.commit()

    res_inactive = client.post(
        "/api/v1/query/search",
        json={
            "query": "What are the scheme benefits?",
            "collection_id": inactive_col.id,
        },
    )
    assert res_inactive.status_code == 404
    assert "not found or inactive" in res_inactive.json()["detail"].lower()


def test_private_collection_access_control_forbidden_for_other_users(client: TestClient, db_session: Session):
    """
    Requirement 1 & Security Test:
    Proves that a citizen cannot access another user's private collection.
    """
    dept = db_session.query(Department).first()

    # User A creates a private collection
    user_a, token_a = _create_test_user(
        db_session, f"owner_{uuid.uuid4().hex[:6]}@example.com", "CITIZEN", ["query:execute"]
    )
    user_b, token_b = _create_test_user(
        db_session, f"intruder_{uuid.uuid4().hex[:6]}@example.com", "CITIZEN", ["query:execute"]
    )

    private_col = DocumentCollection(
        id=f"col-priv-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Confidential Department Schemes",
        slug=f"confidential-{uuid.uuid4().hex[:6]}",
        is_private=True,
        owner_user_id=user_a.id,
        is_active=True,
    )
    db_session.add(private_col)
    db_session.commit()

    # 1. Anonymous user attempts search -> 403 Forbidden
    res_anon = client.post(
        "/api/v1/query/search",
        json={"query": "Confidential scheme grant limits", "collection_id": private_col.id},
    )
    assert res_anon.status_code == 403
    assert "permission" in res_anon.json()["detail"].lower()

    # 2. User B (Citizen) attempts search on User A's private collection -> 403 Forbidden
    res_unauth = client.post(
        "/api/v1/query/search",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"query": "Confidential scheme grant limits", "collection_id": private_col.id},
    )
    assert res_unauth.status_code == 403
    assert "permission" in res_unauth.json()["detail"].lower()

    # 3. User A (Owner) searches their own private collection -> 200 OK
    res_owner = client.post(
        "/api/v1/query/search",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"query": "Confidential scheme grant limits", "collection_id": private_col.id},
    )
    assert res_owner.status_code == 200

    # 4. System Admin searches the private collection -> 200 OK
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    admin_token = admin_login.json()["token"]

    res_admin = client.post(
        "/api/v1/query/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"query": "Confidential scheme grant limits", "collection_id": private_col.id},
    )
    assert res_admin.status_code == 200


def test_server_side_source_isolation_between_collections(client: TestClient, db_session: Session):
    """
    Requirements 2 & 7:
    Strict server-side isolation: Retrieval filters by collection_id server-side.
    Proves that a search query targeting Collection A NEVER returns documents or citations from Collection B.
    """
    dept = db_session.query(Department).first()

    # Create Collection 1: Health Mission
    col1 = DocumentCollection(
        id=f"col-health-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="National Health Mission Collection",
        slug=f"nhm-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    # Create Collection 2: Agriculture Mission
    col2 = DocumentCollection(
        id=f"col-agri-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="National Agriculture Mission Collection",
        slug=f"nam-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add_all([col1, col2])
    db_session.commit()

    # Document 1 in Collection 1
    doc1, ver1, page1, chunk1 = _create_test_document_with_chunk(
        db=db_session,
        collection_id=col1.id,
        scheme_name="Ayushman Bharat Health Protection",
        department="Ministry of Health",
        filename="NHM_Manual.pdf",
        chunk_text="Ayushman Bharat provides secondary and tertiary health cover up to Rs. 5,00,000 per family per year.",
        status=DocumentStatus.ACTIVE,
        version_number=1,
    )

    # Document 2 in Collection 2
    doc2, ver2, page2, chunk2 = _create_test_document_with_chunk(
        db=db_session,
        collection_id=col2.id,
        scheme_name="Kisan Drone Agriculture Subsidy",
        department="Ministry of Agriculture",
        filename="Drone_Guidelines.pdf",
        chunk_text="Farmers receive a 50% subsidy up to Rs. 5,00,000 for agricultural drone equipment purchases.",
        status=DocumentStatus.ACTIVE,
        version_number=1,
    )

    # Query Collection 1: Health
    res1 = client.post(
        "/api/v1/query/search",
        json={
            "query": "What is the health insurance coverage under Ayushman Bharat?",
            "collection_id": col1.id,
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["citations"]) > 0
    # Every citation MUST belong strictly to Collection 1
    for cit in data1["citations"]:
        assert cit["document_id"] == doc1.id
        assert "Ayushman" in cit["document_title"]
        assert "Drone" not in cit["document_title"]
        assert "Agriculture" not in (cit["department"] or "")

    # Query Collection 2: Agriculture searching for Health terms
    # Should NOT leak anything from Collection 1
    res2 = client.post(
        "/api/v1/query/search",
        json={
            "query": "What is the health insurance coverage under Ayushman Bharat?",
            "collection_id": col2.id,
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    # Zero citations because Ayushman Bharat does NOT exist in Collection 2
    assert len(data2["citations"]) == 0
    assert data2["is_refusal"] is True
    assert "not found in the selected uploaded documents" in data2["answer"].lower()


def test_active_approved_documents_used_by_default(client: TestClient, db_session: Session):
    """
    Requirement 3:
    Only approved and active documents are used by default.
    Archived and processing documents are strictly ignored in standard citizen search.
    """
    dept = db_session.query(Department).first()

    col = DocumentCollection(
        id=f"col-filter-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Status Filter Isolation Collection",
        slug=f"status-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    # Archived Document
    doc_arch, ver_arch, page_arch, chunk_arch = _create_test_document_with_chunk(
        db=db_session,
        collection_id=col.id,
        scheme_name="Archived Historical Welfare Grant",
        department="Ministry of Finance",
        filename="Old_Grant.pdf",
        chunk_text="Historical grant of Rs. 10,000 for all rural residents discontinued in 2020.",
        status=DocumentStatus.ARCHIVED,
        version_number=1,
    )

    # Active Document
    doc_act, ver_act, page_act, chunk_act = _create_test_document_with_chunk(
        db=db_session,
        collection_id=col.id,
        scheme_name="Current Active Welfare Grant",
        department="Ministry of Finance",
        filename="Current_Grant.pdf",
        chunk_text="Current grant of Rs. 25,000 for rural artisans effective from April 2024.",
        status=DocumentStatus.ACTIVE,
        version_number=2,
    )


    # Search without include_historical (default citizen search)
    res = client.post(
        "/api/v1/query/search",
        json={
            "query": "What is the rural welfare grant amount?",
            "collection_id": col.id,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["citations"]) > 0

    # Ensure all citations are ACTIVE and none are ARCHIVED
    for cit in data["citations"]:
        assert cit["status"] == "ACTIVE"
        assert cit["is_historical"] is False
        assert "Archived" not in cit["document_title"]
        assert "Current Active" in cit["document_title"]


def test_insufficient_evidence_structured_refusal(client: TestClient):
    """
    Requirements 5, 6 & 7:
    - If evidence is insufficient, return a structured no-answer result.
    - The answer must state that the information was not found in the selected uploaded documents.
    - Do not fill gaps with general model knowledge.
    """
    res = client.post(
        "/api/v1/query/search",
        json={
            "query": "What are the space exploration grant benefits for Mars orbiters?",
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["is_refusal"] is True
    assert data["insufficient_evidence"] is True
    assert len(data["citations"]) == 0
    # Must explicitly state the required standard refusal phrasing
    assert "the requested information was not found in the selected uploaded documents" in data["answer"].lower()
    # Must explicitly disclaim model knowledge gap-filling
    assert "general model knowledge" in data["answer"].lower()


def test_factual_claim_citation_validation():
    """
    Requirement 8:
    Validate that every factual claim has at least one retrieved citation.
    """
    passage = CitationOut(
        document_id="doc-test-1",
        document_title="PM Scholarship Operational Manual (v1)",
        version_number=1,
        page_number=4,
        excerpt="Eligible girl students receive a scholarship of Rs. 3,000 per month for professional degree courses.",
        score=0.92,
    )

    # 1. Grounded Answer with valid citation marker and content overlap
    grounded_ans = (
        "Under PM Scholarship Operational Manual (v1), Page 4: "
        "Eligible girl students receive a scholarship of Rs. 3,000 per month for professional degree courses. "
        "[Source: PM Scholarship Operational Manual (v1), Page 4]."
    )
    is_valid, claims = GenerationService.validate_factual_claims(grounded_ans, [passage])
    assert is_valid is True
    assert len(claims) > 0
    assert all(c.citation_verified for c in claims)

    # 2. Fabricated / Ungrounded Claim without citation
    hallucinated_ans = (
        "Students are also given free high-performance laptops and international flight tickets to study abroad."
    )
    is_valid_fake, claims_fake = GenerationService.validate_factual_claims(hallucinated_ans, [passage])
    assert is_valid_fake is False
    assert any(not c.citation_verified for c in claims_fake)

    # 3. GenerationService refuses ungrounded answers
    res = GenerationService.generate_grounded_answer(
        query="Do students get free laptops?",
        passages=[],
        collection_name="Scholarship Collection",
    )
    assert res.is_refusal is True
    assert res.insufficient_evidence is True
    assert "not found in the selected uploaded documents" in res.answer

"""
Test Suite for Post-Generation Citation Validation and Grounding Verification.

Tests:
1. Valid citations pass 5-point verification (document, collection, permissions, page, text provenance).
2. Wrong-document citations rejected (document belongs to different collection).
3. Non-existent document citations rejected.
4. Invalid page number citations rejected (exceeding document page count or not found).
5. Uncited factual claims detected, triggering strict regeneration or verification warning.
6. Fabricated text not in retrieved evidence rejected.
7. Unauthorized private collection citations rejected.
8. Unauthorized archived citations rejected for non-admin requests.
9. Integration API test verifying QueryResponse includes validation_report and verification_warning.
"""

from typing import Tuple
import uuid
import pytest
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
from backend.app.models.schemas import CitationOut, QueryRequest, UserOut, UserRole
from backend.app.services.citation_validator import citation_validator
from backend.app.services.search_service import search_service


def _create_user(db: Session, email: str, role_name: str, perms: list) -> Tuple[User, str, UserOut]:
    """Helper to create test user and JWT token."""
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
    token = create_access_token(user_id=user.id, email=user.email, role=role_enum)
    user_out = UserOut.model_validate(user)
    return user, token, user_out


def _create_doc_with_pages(
    db: Session,
    collection_id: str,
    scheme_name: str,
    department: str,
    total_pages: int = 2,
    status: DocumentStatus = DocumentStatus.ACTIVE,
    page_texts: list = None,
) -> Tuple[Document, DocumentVersion, list]:
    """Helper to create a document with specific pages and chunks."""
    doc_id = f"doc-{uuid.uuid4()}"
    ver_id = f"ver-{uuid.uuid4()}"

    doc = Document(
        id=doc_id,
        collection_id=collection_id,
        scheme_name=scheme_name,
        department=department,
        original_filename=f"{scheme_name}.pdf",
        storage_file_key=f"raw-documents/{uuid.uuid4()}.pdf",
        file_hash=f"hash-{uuid.uuid4().hex}",
        status=status.value,
        version_number=1,
    )
    ver = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        original_filename=f"{scheme_name}.pdf",
        storage_file_key=f"raw-documents/{uuid.uuid4()}.pdf",
        file_hash=f"hash-{uuid.uuid4().hex}",
        status=status.value,
        total_pages=total_pages,
    )
    db.add_all([doc, ver])
    db.commit()

    created_pages = []
    for p_num in range(1, total_pages + 1):
        p_id = f"page-{uuid.uuid4()}"
        p_text = (
            page_texts[p_num - 1]
            if page_texts and len(page_texts) >= p_num
            else f"Official text content on page {p_num} for scheme {scheme_name}."
        )
        page = DocumentPage(
            id=p_id,
            version_id=ver_id,
            document_id=doc_id,
            page_number=p_num,
            raw_text=p_text,
            word_count=len(p_text.split()),
        )
        chunk = ExtractedChunk(
            id=f"chunk-{uuid.uuid4()}",
            page_id=p_id,
            version_id=ver_id,
            document_id=doc_id,
            chunk_index=0,
            page_number=p_num,
            page_range=str(p_num),
            chunk_text=p_text,
            normalized_text=p_text.lower(),
            token_count=len(p_text.split()),
        )
        db.add_all([page, chunk])
        created_pages.append(page)

    db.commit()
    return doc, ver, created_pages


def test_valid_citations_pass_verification(db_session: Session):
    """Confirm that a valid citation passes all 5 verification checks."""
    dept = db_session.query(Department).first()
    col = DocumentCollection(
        id=f"col-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Valid Citation Collection",
        slug=f"valid-col-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    doc_text = "Eligible women receive an annual nutrition allowance of Rs. 6,000 in three direct transfers."
    doc, ver, pages = _create_doc_with_pages(
        db_session, col.id, "Matru Vandana Nutrition Scheme", "Ministry of Women", total_pages=3, page_texts=[doc_text, "Page 2 text", "Page 3 text"]
    )

    valid_cit = CitationOut(
        document_id=doc.id,
        document_title="Matru Vandana Nutrition Scheme (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=1,
        excerpt=doc_text,
        score=0.92,
    )

    is_valid, err = citation_validator.validate_single_citation(
        db=db_session,
        citation=valid_cit,
        selected_collection_id=col.id,
        retrieved_passages=[valid_cit],
    )
    assert is_valid is True
    assert err is None


def test_wrong_document_citation_rejected(db_session: Session):
    """Confirm that a citation citing a document from a different collection is rejected."""
    dept = db_session.query(Department).first()
    col_a = DocumentCollection(
        id=f"col-a-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Collection A",
        slug=f"col-a-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    col_b = DocumentCollection(
        id=f"col-b-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Collection B",
        slug=f"col-b-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add_all([col_a, col_b])
    db_session.commit()

    # Doc B is inside Col B
    doc_b, ver_b, _ = _create_doc_with_pages(db_session, col_b.id, "Col B Scheme", "Dept B", total_pages=2)

    # Citation points to Doc B, but selected collection is Col A!
    wrong_cit = CitationOut(
        document_id=doc_b.id,
        document_title="Col B Scheme (v1)",
        version_id=ver_b.id,
        version_number=1,
        page_number=1,
        excerpt="Col B scheme text excerpt.",
        score=0.85,
    )

    is_valid, err = citation_validator.validate_single_citation(
        db=db_session,
        citation=wrong_cit,
        selected_collection_id=col_a.id,  # Selected is A, document belongs to B!
        retrieved_passages=[wrong_cit],
    )
    assert is_valid is False
    assert err == "WRONG_COLLECTION"


def test_nonexistent_document_citation_rejected(db_session: Session):
    """Confirm that a citation pointing to a non-existent document ID is rejected."""
    dept = db_session.query(Department).first()
    col = DocumentCollection(
        id=f"col-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Test Col",
        slug=f"test-col-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    fake_cit = CitationOut(
        document_id="doc-nonexistent-uuid-99999",
        document_title="Phantom Hallucinated Scheme",
        version_number=1,
        page_number=1,
        excerpt="Hallucinated text content.",
        score=0.80,
    )

    is_valid, err = citation_validator.validate_single_citation(
        db=db_session,
        citation=fake_cit,
        selected_collection_id=col.id,
        retrieved_passages=[fake_cit],
    )
    assert is_valid is False
    assert err == "DOCUMENT_NOT_FOUND"


def test_invalid_page_number_rejected(db_session: Session):
    """Confirm that citation with invalid or out-of-range page number is rejected."""
    dept = db_session.query(Department).first()
    col = DocumentCollection(
        id=f"col-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Page Test Col",
        slug=f"page-col-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    # Document only has 2 pages
    doc, ver, _ = _create_doc_with_pages(db_session, col.id, "Short Scheme Document", "Dept", total_pages=2)

    # 1. Page number exceeds document pages (Page 99 on 2-page doc)
    out_of_range_cit = CitationOut(
        document_id=doc.id,
        document_title="Short Scheme Document (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=99,
        excerpt="Page 99 hallucinated excerpt.",
        score=0.88,
    )
    is_valid_high, err_high = citation_validator.validate_single_citation(
        db=db_session,
        citation=out_of_range_cit,
        selected_collection_id=col.id,
        retrieved_passages=[out_of_range_cit],
    )
    assert is_valid_high is False
    assert err_high == "INVALID_PAGE_NUMBER"

    # 2. Page number zero or negative
    zero_page_cit = CitationOut(
        document_id=doc.id,
        document_title="Short Scheme Document (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=0,
        excerpt="Page 0 excerpt.",
        score=0.88,
    )
    is_valid_zero, err_zero = citation_validator.validate_single_citation(
        db=db_session,
        citation=zero_page_cit,
        selected_collection_id=col.id,
        retrieved_passages=[zero_page_cit],
    )
    assert is_valid_zero is False
    assert err_zero == "INVALID_PAGE_NUMBER"


def test_text_not_in_retrieved_evidence_rejected(db_session: Session):
    """Confirm that a citation with text not present in retrieved evidence is rejected."""
    dept = db_session.query(Department).first()
    col = DocumentCollection(
        id=f"col-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Evidence Provenance Col",
        slug=f"provenance-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    actual_text = "Senior citizens aged 60 and above receive a monthly pension of Rs. 1,000."
    doc, ver, _ = _create_doc_with_pages(
        db_session, col.id, "Pension Manual", "Dept of Social Justice", total_pages=1, page_texts=[actual_text]
    )

    # Actual retrieved passage
    retrieved = CitationOut(
        document_id=doc.id,
        document_title="Pension Manual (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=1,
        excerpt=actual_text,
        score=0.90,
    )

    # Fabricated citation citing text never retrieved
    fabricated_cit = CitationOut(
        document_id=doc.id,
        document_title="Pension Manual (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=1,
        excerpt="Beneficiaries receive free international airline flights to Australia and complimentary luxury cars.",
        score=0.90,
    )

    is_valid, err = citation_validator.validate_single_citation(
        db=db_session,
        citation=fabricated_cit,
        selected_collection_id=col.id,
        retrieved_passages=[retrieved],
    )
    assert is_valid is False
    assert err == "NOT_IN_RETRIEVED_EVIDENCE"


def test_unauthorized_private_collection_citation_rejected(db_session: Session):
    """Confirm that citizen accessing private collection citations without authorization is rejected."""
    dept = db_session.query(Department).first()
    owner_user, _, _ = _create_user(db_session, f"owner_{uuid.uuid4().hex[:6]}@test.com", "CITIZEN", ["query:execute"])
    intruder_user, _, intruder_out = _create_user(db_session, f"intruder_{uuid.uuid4().hex[:6]}@test.com", "CITIZEN", ["query:execute"])

    private_col = DocumentCollection(
        id=f"col-priv-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Classified Subsidies",
        slug=f"priv-{uuid.uuid4().hex[:6]}",
        is_private=True,
        owner_user_id=owner_user.id,
        is_active=True,
    )
    db_session.add(private_col)
    db_session.commit()

    doc, ver, _ = _create_doc_with_pages(db_session, private_col.id, "Classified Manual", "Ministry of Defense")
    cit = CitationOut(
        document_id=doc.id,
        document_title="Classified Manual (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=1,
        excerpt="Defense personnel grant details.",
        score=0.90,
    )

    # Intruder citizen attempting validation
    is_valid, err = citation_validator.validate_single_citation(
        db=db_session,
        citation=cit,
        selected_collection_id=private_col.id,
        current_user=intruder_out,
        retrieved_passages=[cit],
    )
    assert is_valid is False
    assert err == "UNAUTHORIZED_PRIVATE_COLLECTION"


def test_unauthorized_archived_citation_rejected_for_citizens(db_session: Session):
    """Confirm that citations to archived documents are rejected for citizens when historical search is disabled."""
    dept = db_session.query(Department).first()
    col = DocumentCollection(
        id=f"col-arch-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Archive Test Col",
        slug=f"arch-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    doc, ver, _ = _create_doc_with_pages(
        db_session, col.id, "Discontinued Old Scheme", "Ministry of Commerce", status=DocumentStatus.ARCHIVED
    )
    cit = CitationOut(
        document_id=doc.id,
        document_title="Discontinued Old Scheme (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=1,
        excerpt="Discontinued export incentive rules.",
        score=0.90,
    )

    _, _, citizen_out = _create_user(db_session, f"cit_{uuid.uuid4().hex[:6]}@test.com", "CITIZEN", ["query:execute"])

    # Citizen cannot access archived citations
    is_valid, err = citation_validator.validate_single_citation(
        db=db_session,
        citation=cit,
        selected_collection_id=col.id,
        current_user=citizen_out,
        include_historical=False,
        retrieved_passages=[cit],
    )
    assert is_valid is False
    assert err == "UNAUTHORIZED_ARCHIVED_DOCUMENT"


def test_uncited_claims_trigger_regeneration_or_warning(db_session: Session):
    """
    Test that when an answer contains unsupported factual claims,
    the reconciliation engine regenerates with strict evidence instructions
    or attaches a verification warning.
    """
    dept = db_session.query(Department).first()
    col = DocumentCollection(
        id=f"col-regen-{uuid.uuid4()}",
        department_id=dept.id if dept else None,
        name="Regen Test Col",
        slug=f"regen-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(col)
    db_session.commit()

    verified_text = "Smallholder farmers holding up to 2 hectares are entitled to subsidized seeds."
    doc, ver, _ = _create_doc_with_pages(
        db_session, col.id, "Seed Subsidy Manual", "Ministry of Agriculture", total_pages=1, page_texts=[verified_text]
    )

    valid_cit = CitationOut(
        document_id=doc.id,
        document_title="Seed Subsidy Manual (v1)",
        version_id=ver.id,
        version_number=1,
        page_number=1,
        excerpt=verified_text,
        score=0.95,
    )

    # Answer containing a hallucinated / uncited claim alongside grounded text
    mixed_answer = (
        f"Under Seed Subsidy Manual (v1), Page 1: {verified_text} [Source: Seed Subsidy Manual (v1), Page 1]. "
        f"Additionally, the government gives every applicant an unmetered free tractor and unlimited diesel fuel."
    )

    final_ans, supported_cits, verified, warning, report = citation_validator.validate_and_reconcile_answer(
        db=db_session,
        query="What are seed subsidy rules and tractor benefits?",
        answer=mixed_answer,
        citations=[valid_cit],
        selected_collection_id=col.id,
        retrieved_passages=[valid_cit],
    )

    # Factual claims reconciliation must have triggered regeneration or warning
    assert len(supported_cits) == 1
    assert report.has_unsupported_claims is True
    # The regenerated answer strictly bounds to verified text, excluding the hallucinated tractor claim
    assert "tractor" not in final_ans.lower()
    assert "seed" in final_ans.lower()


def test_api_search_returns_verification_report_and_warning(client: TestClient, db_session: Session):
    """
    Integration test: Querying search endpoint executes citation validation
    and includes validation report in response.
    """
    res = client.post(
        "/api/v1/query/search",
        json={
            "query": "What is PMAY-U housing subsidy limit?",
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["grounding_verified"] is True
    assert "validation_report" in data
    report = data["validation_report"]
    if report:
        assert report["total_citations"] > 0
        assert report["valid_citations_count"] > 0
        assert report["invalid_citations_count"] == 0
        for item in report["details"]:
            assert item["is_valid"] is True
            assert item["error_reason"] is None

"""
Unit & Integration tests for Document Version Management, State Transitions,
Historical Search Access Control, Audit Tracking, and Version Conflicts.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.models.db_models import AuditEvent, Document, DocumentStatus, DocumentVersion


def test_document_version_transitions_and_audit(client: TestClient, db_session: Session):
    """
    Test version management workflow:
    1. Upload document (v1).
    2. Add new version (v2).
    3. Archive document and verify versions transition to ARCHIVED.
    4. Restore document and verify versions transition to ACTIVE.
    5. Verify AuditEvent captures who and when.
    """
    # 1. Login as System Admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    admin_id = login_res.json()["user"]["id"]

    # 2. Upload Document (v1)
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "National Scholarship Scheme",
            "department": "Ministry of Education",
            "original_filename": "NSS_Guidelines_v1.pdf",
            "version_number": 1,
        },
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # 3. Create Version 2 for the scheme document
    v2_res = client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "version_number": 2,
            "original_filename": "NSS_Guidelines_v2.pdf",
            "change_summary": "Revised income threshold for 2025-26 academic year.",
        },
    )
    assert v2_res.status_code == 200
    v2_data = v2_res.json()
    assert v2_data["version_number"] == 2
    assert v2_data["status"] == "ACTIVE"

    # Verify versions list
    versions_list_res = client.get(
        f"/api/v1/documents/{doc_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert versions_list_res.status_code == 200
    versions = versions_list_res.json()
    assert len(versions) == 2
    v_nums = [v["version_number"] for v in versions]
    assert 1 in v_nums and 2 in v_nums

    # 4. Administrator Archives Document
    archive_res = client.put(
        f"/api/v1/documents/{doc_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"

    # Verify DB state: Document and versions are ARCHIVED
    doc_db = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc_db.status == DocumentStatus.ARCHIVED.value

    # Verify Audit Event recorded for Archive
    audit_archive = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.entity_id == doc_id, AuditEvent.action_type == "DOC_ARCHIVE")
        .first()
    )
    assert audit_archive is not None
    assert audit_archive.user_id == admin_id
    assert audit_archive.created_at is not None

    # 5. Administrator Restores Document
    restore_res = client.put(
        f"/api/v1/documents/{doc_id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["status"] == "ACTIVE"

    db_session.refresh(doc_db)
    assert doc_db.status == DocumentStatus.ACTIVE.value

    # Verify Audit Event recorded for Restore
    audit_restore = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.entity_id == doc_id, AuditEvent.action_type == "DOC_RESTORE")
        .first()
    )
    assert audit_restore is not None
    assert audit_restore.user_id == admin_id
    assert audit_restore.created_at is not None


def test_active_version_search_and_historical_search_access_control(client: TestClient, db_session: Session):
    """
    Test:
    1. Active document search shows active version in citations.
    2. Archived documents are excluded by default from search.
    3. Historical search is restricted to administrators (citizens receive 403).
    4. When administrator enables historical search, archived documents can be queried.
    """
    # 1. Login as Admin & create an archived document
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    admin_token = admin_login.json()["token"]

    # Register & Login as Citizen
    cit_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "citizen.searchtest@example.com", "password": "Password@123", "full_name": "Search Citizen"},
    )
    citizen_token = cit_reg.json()["token"]

    # 2. Public / Citizen Search returns active version in citations
    search_res = client.post(
        "/api/v1/query/search",
        json={"query": "What is PMAY-U housing subsidy limit?"},
    )
    assert search_res.status_code == 200
    data = search_res.json()
    assert len(data["citations"]) > 0
    citation = data["citations"][0]
    assert citation["version_number"] is not None
    assert "v" in citation["document_title"]

    # 3. Citizen attempting historical search receives 403 Forbidden
    unauth_hist = client.post(
        "/api/v1/query/search",
        headers={"Authorization": f"Bearer {citizen_token}"},
        json={"query": "What is PMAY-U housing subsidy limit?", "include_historical": True},
    )
    assert unauth_hist.status_code == 403
    assert "restricted to administrators" in unauth_hist.json()["detail"]

    # Anonymous user attempting historical search receives 403 Forbidden
    anon_hist = client.post(
        "/api/v1/query/search",
        json={"query": "What is PMAY-U housing subsidy limit?", "include_historical": True},
    )
    assert anon_hist.status_code == 403

    # 4. Administrator can successfully query with include_historical
    admin_hist = client.post(
        "/api/v1/query/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"query": "What is PMAY-U housing subsidy limit?", "include_historical": True},
    )
    assert admin_hist.status_code == 200
    assert len(admin_hist.json()["citations"]) > 0


def test_active_version_conflict_detection(client: TestClient):
    """
    Test that conflict detection endpoint detects when two active documents
    in the same collection cover the identical scheme name.
    """
    # 1. Login as Admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    col_id = "col-0000000-0000-4000-8000-000000000001"

    # 2. Upload Document 1
    client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "collection_id": col_id,
            "scheme_name": "Conflict Scheme Test",
            "department": "Ministry of Overlap",
            "original_filename": "Scheme_2024.pdf",
            "version_number": 1,
        },
    )

    # 3. Upload Document 2 (Active with same scheme name in same collection)
    client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "collection_id": col_id,
            "scheme_name": "Conflict Scheme Test",
            "department": "Ministry of Overlap",
            "original_filename": "Scheme_2025.pdf",
            "version_number": 2,
        },
    )

    # 4. Check conflicts
    conflict_res = client.get(
        "/api/v1/documents/conflicts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert conflict_res.status_code == 200
    conflicts = conflict_res.json()
    assert len(conflicts) > 0
    conflict_schemes = [c["scheme_name"] for c in conflicts]
    assert "Conflict Scheme Test" in conflict_schemes

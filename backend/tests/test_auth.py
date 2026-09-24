"""
Integration and Unit tests for Authentication, JWT generation, Session Expiration,
and Server-Side Role-Based Access Control (RBAC) Enforcement across all 3 roles:
- Citizen
- Helpdesk Staff
- Administrator
"""

from datetime import timedelta
from fastapi.testclient import TestClient
from backend.app.core.security import create_access_token
from backend.app.models.schemas import UserRole


# -----------------------------------------------------------------------------
# 1. Citizen Authentication & Permissions Tests
# -----------------------------------------------------------------------------

def test_citizen_registration_and_login(client: TestClient):
    """Test public citizen self-registration and subsequent login."""
    # 1. Register
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "citizen.priya@example.com",
            "password": "Password@123",
            "full_name": "Priya Sharma",
        },
    )
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["user"]["role"] == "CITIZEN"
    assert "query:execute" in reg_data["user"]["permissions"]

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "citizen.priya@example.com",
            "password": "Password@123",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["token"]
    assert token is not None

    # 3. Citizen can search
    search_res = client.post(
        "/api/v1/query/search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "What is PMAY-U income limit?",
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
        },
    )
    assert search_res.status_code == 200

    # 4. Citizen cannot upload documents (Forbidden 403)
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Unauthorized Scheme",
            "department": "Department of Unauthorized",
            "original_filename": "test.pdf",
        },
    )
    assert upload_res.status_code == 403

    # 5. Citizen cannot view audit logs (Forbidden 403)
    audit_res = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_res.status_code == 403

    # 6. Citizen logout
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200


# -----------------------------------------------------------------------------
# 2. Helpdesk Staff Role & Server-Side Enforcement Tests
# -----------------------------------------------------------------------------

def test_helpdesk_staff_authorized_and_restricted_actions(client: TestClient):
    """Test that Helpdesk staff can use eligibility checks, history, and feedback, but cannot upload/archive documents."""
    # 1. Login as Helpdesk staff
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "email": "helpdesk.staff@welfareconnect.local",
            "password": "Staff@123456",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # 2. Helpdesk can run eligibility evaluation
    elig_res = client.post(
        "/api/v1/query/eligibility",
        headers={"Authorization": f"Bearer {token}"},
        json={"annual_income": 250000, "landholding_hectares": 1.5},
    )
    assert elig_res.status_code == 200
    elig_data = elig_res.json()
    assert len(elig_data["eligible_schemes"]) > 0

    # 3. Helpdesk can view query history
    hist_res = client.get(
        "/api/v1/query/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert hist_res.status_code == 200

    # 4. Helpdesk CANNOT upload documents (403 Forbidden)
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Helpdesk Test Scheme",
            "department": "Ministry of Helpdesk",
            "original_filename": "sample.pdf",
        },
    )
    assert upload_res.status_code == 403

    # 5. Helpdesk CANNOT archive documents (403 Forbidden)
    archive_res = client.put(
        "/api/v1/documents/doc-0000000-0000-4000-8000-000000000001/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archive_res.status_code == 403

    # 6. Helpdesk CANNOT view audit logs (403 Forbidden)
    audit_res = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_res.status_code == 403


# -----------------------------------------------------------------------------
# 3. Administrator Role & Privileged Actions Tests
# -----------------------------------------------------------------------------

def test_administrator_full_lifecycle_and_audit(client: TestClient):
    """Test administrator document upload, processing, archiving, deletion, and audit logging."""
    # 1. Login as System Admin
    admin_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin.dev@welfareconnect.local",
            "password": "Admin@123456",
        },
    )
    assert admin_login.status_code == 200
    token = admin_login.json()["token"]

    # 2. Admin creates collection
    col_res = client.post(
        "/api/v1/collections",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Social Security Pensions",
            "slug": "social-security-pensions",
            "description": "Old age and disability pension guidelines",
        },
    )
    assert col_res.status_code == 200
    col_id = col_res.json()["id"]

    # 3. Admin uploads document
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "collection_id": col_id,
            "scheme_name": "National Social Assistance Programme",
            "department": "Ministry of Rural Development",
            "original_filename": "NSAP_Guidelines_2024.pdf",
        },
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # 4. Admin processes document
    proc_res = client.post(
        "/api/v1/documents/{}/process".format(doc_id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert proc_res.status_code == 200
    assert proc_res.json()["action"] == "PROCESS"

    # 5. Admin archives document
    archive_res = client.put(
        "/api/v1/documents/{}/archive".format(doc_id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"

    # 6. Admin deletes document
    del_res = client.delete(
        "/api/v1/documents/{}".format(doc_id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "DELETED"

    # 7. Admin views audit logs
    audit_res = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert "USER_LOGIN" in actions


# -----------------------------------------------------------------------------
# 4. Token Validation, Security & Expiration Tests
# -----------------------------------------------------------------------------

def test_unauthenticated_request_fails(client: TestClient):
    """Verify that requests without token are rejected with 401."""
    res = client.post(
        "/api/v1/documents/upload",
        json={
            "collection_id": "col-123",
            "scheme_name": "Test",
            "department": "Test",
            "original_filename": "test.pdf",
        },
    )
    assert res.status_code == 401


def test_expired_token_fails(client: TestClient):
    """Verify that an expired token is rejected with 401."""
    expired_token = create_access_token(
        user_id="b0000000-0000-4000-8000-000000000001",
        email="admin.dev@welfareconnect.local",
        role=UserRole.SYSTEM_ADMIN,
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )

    res = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "Invalid or expired token" in res.json()["detail"]

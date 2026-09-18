"""
Integration and Unit tests for Authentication, JWT generation, and Role-Based Access Control (RBAC).
Preserves and validates Prompt 05 authentication rules.
"""

from fastapi.testclient import TestClient


def test_dev_admin_login(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin.dev@welfareconnect.local",
            "password": "Admin@123456",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["role"] == "SYSTEM_ADMIN"
    assert "admin:all" in data["user"]["permissions"]


def test_helpdesk_staff_login(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "helpdesk.staff@welfareconnect.local",
            "password": "Staff@123456",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["role"] == "HELPDESK"
    assert "eligibility:check" in data["user"]["permissions"]


def test_invalid_login_credentials(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin.dev@welfareconnect.local",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_citizen_registration(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "citizen.test@example.com",
            "password": "SecurePassword123",
            "full_name": "Ramesh Citizen",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "CITIZEN"
    assert data["user"]["email"] == "citizen.test@example.com"
    assert "query:execute" in data["user"]["permissions"]


def test_admin_create_staff_account(client: TestClient):
    # 1. Login as Admin
    admin_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin.dev@welfareconnect.local",
            "password": "Admin@123456",
        },
    )
    admin_token = admin_login.json()["token"]

    # 2. Create new Scheme Admin
    response = client.post(
        "/api/v1/auth/staff",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "scheme.officer@welfareconnect.local",
            "password": "Officer@123456",
            "full_name": "Scheme Nodal Officer",
            "role": "SCHEME_ADMIN",
            "department": "Ministry of Housing",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "SCHEME_ADMIN"
    assert "docs:upload" in data["permissions"]


def test_non_admin_cannot_create_staff(client: TestClient):
    # 1. Login as Helpdesk
    staff_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "helpdesk.staff@welfareconnect.local",
            "password": "Staff@123456",
        },
    )
    staff_token = staff_login.json()["token"]

    # 2. Try creating staff (should be 403 Forbidden)
    response = client.post(
        "/api/v1/auth/staff",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={
            "email": "unauthorized@example.com",
            "password": "Password123",
            "full_name": "Hacker",
            "role": "SYSTEM_ADMIN",
        },
    )
    assert response.status_code == 403


def test_get_current_user_profile(client: TestClient):
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin.dev@welfareconnect.local",
            "password": "Admin@123456",
        },
    )
    token = login.json()["token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin.dev@welfareconnect.local"
    assert data["role"] == "SYSTEM_ADMIN"

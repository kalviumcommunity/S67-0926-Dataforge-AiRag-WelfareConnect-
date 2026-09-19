"""
Unit and Integration tests for Administrator Document Upload & Collection Management.
Tests frontend-ready endpoints, file validation, file size limits, duplicate warnings,
and metadata persistence.
"""

import io
from fastapi.testclient import TestClient
from backend.app.config import settings
from backend.app.models.schemas import UserRole


from backend.app.services.document_service import _generate_sample_pdf


def test_admin_upload_binary_pdf(client: TestClient):
    """Test successful multipart PDF upload with full metadata."""
    # 1. Admin Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    # 2. Upload valid PDF
    pdf_bytes = _generate_sample_pdf("Atal Pension Yojana (APY)", "Department of Financial Services", 1)
    dummy_pdf = io.BytesIO(pdf_bytes)
    
    upload_res = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Atal Pension Yojana (APY)",
            "department": "Department of Financial Services",
            "state_or_district": "National / All States",
            "language": "en",
            "publication_date": "2024-01-01T00:00:00Z",
            "effective_date": "2024-04-01T00:00:00Z",
            "version_number": "1",
            "visibility": "public",
            "is_official_source_confirmed": "true",
        },
        files={"file": ("APY_Scheme_Guidelines.pdf", dummy_pdf, "application/pdf")},
    )
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert data["title"] == "Atal Pension Yojana (APY)"
    assert data["department"] == "Department of Financial Services"
    assert data["language"] == "en"
    assert data["current_version"] == 1
    assert data["status"] == "ACTIVE"
    assert data["file_hash"] is not None


def test_admin_upload_rejects_non_pdf(client: TestClient):
    """Test that uploading a non-PDF file returns 400."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    dummy_exe = io.BytesIO(b"malicious executable content")
    upload_res = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Executable Test",
            "department": "Security Department",
            "is_official_source_confirmed": "true",
        },
        files={"file": ("malware.exe", dummy_exe, "application/octet-stream")},
    )
    assert upload_res.status_code == 400
    assert "Only official PDF documents" in upload_res.json()["detail"]


def test_admin_upload_duplicate_detection(client: TestClient):
    """Test duplicate file hash warning detection on identical content upload."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    identical_content = _generate_sample_pdf("Duplicate Test Scheme", "Ministry of Urban Affairs", 1)
    
    # First upload
    res1 = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Original Circular Scheme",
            "department": "Ministry of Urban Affairs",
            "is_official_source_confirmed": "true",
        },
        files={"file": ("original_circular.pdf", io.BytesIO(identical_content), "application/pdf")},
    )
    assert res1.status_code == 200
    assert res1.json()["duplicate_warning"] is None

    # Second upload with identical file content
    res2 = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Duplicate Circular Scheme",
            "department": "Ministry of Urban Affairs",
            "is_official_source_confirmed": "true",
        },
        files={"file": ("duplicate_circular.pdf", io.BytesIO(identical_content), "application/pdf")},
    )
    assert res2.status_code == 200
    assert res2.json()["duplicate_warning"] is not None
    assert "Duplicate warning" in res2.json()["duplicate_warning"]



def test_admin_upload_rejects_unconfirmed_source(client: TestClient):
    """Test that upload fails if official source is not confirmed."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.dev@welfareconnect.local", "password": "Admin@123456"},
    )
    token = login_res.json()["token"]

    dummy_pdf = io.BytesIO(b"%PDF-1.4\nUnconfirmed source\n%%EOF")
    upload_res = client.post(
        "/api/v1/documents/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "collection_id": "col-0000000-0000-4000-8000-000000000001",
            "scheme_name": "Unconfirmed Scheme",
            "department": "Ministry of Unknown",
            "is_official_source_confirmed": "false",
        },
        files={"file": ("unconfirmed.pdf", dummy_pdf, "application/pdf")},
    )
    assert upload_res.status_code == 400
    assert "official government publication" in upload_res.json()["detail"]

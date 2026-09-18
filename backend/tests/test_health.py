"""
Integration tests for the system health check endpoint.
"""

from fastapi.testclient import TestClient


def test_health_check_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "environment" in data
    assert "components" in data
    assert "database" in data["components"]
    assert data["components"]["database"]["status"] == "healthy"
    assert "vector_store" in data["components"]


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["health_check"] == "/api/v1/health"

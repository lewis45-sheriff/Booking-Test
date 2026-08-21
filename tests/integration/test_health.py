"""
Integration tests for GET /health — Health Check endpoint.

Validates: Requirements 8.1
"""
import pytest


@pytest.mark.django_db
def test_health_check_returns_200(api_client):
    """GET /health returns 200 with {"message": "Service is healthy.", "status": "ok"}."""
    response = api_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Service is healthy."

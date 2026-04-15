"""Tests for health endpoints."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_full_returns_200():
    response = client.get("/api/health/full")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "checks" in data
    assert "version" in data["checks"]

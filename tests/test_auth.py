"""Tests for auth endpoints."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_auth_me_requires_token():
    """GET /api/auth/me without token returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_me_rejects_invalid_bearer():
    """GET /api/auth/me with non-Bearer auth returns 401."""
    response = client.get("/api/auth/me", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


@patch("backend.app.routers.auth.get_firestore_client")
def test_auth_me_dev_bypass_creates_user(mock_get_db):
    """GET /api/auth/me with dev token creates user profile."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer dev-test@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["uid"] == "dev-test@example.com"
    mock_doc_ref.set.assert_called_once()


@patch("backend.app.routers.auth.get_firestore_client")
def test_auth_me_dev_bypass_returns_existing_user(mock_get_db):
    """GET /api/auth/me with dev token returns existing user."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "uid": "dev-test@example.com",
        "email": "test@example.com",
        "display_name": "test",
        "created_at": now,
        "updated_at": now,
    }
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer dev-test@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"

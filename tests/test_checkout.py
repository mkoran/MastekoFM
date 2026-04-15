"""Tests for checkout system."""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer dev-test@example.com"}
AUTH_OTHER = {"Authorization": "Bearer dev-other@example.com"}


def _make_project_doc(owner="dev-test@example.com", checkout=None):
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.id = "proj-1"
    mock_doc.to_dict.return_value = {
        "name": "Test Project",
        "owner_uid": owner,
        "status": "active",
        "checkout": checkout or {},
        "created_at": now,
        "updated_at": now,
    }
    return mock_doc


@patch("backend.app.routers.projects._db")
def test_checkout_acquires_lock(mock_db):
    """POST /checkout acquires a lock."""
    mock_doc = _make_project_doc()
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post("/api/projects/proj-1/checkout", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["checkout"]["user_uid"] == "dev-test@example.com"
    assert data["checkout"]["expires_at"] is not None


@patch("backend.app.routers.projects._db")
def test_checkout_conflict(mock_db):
    """POST /checkout returns 409 if locked by another user."""
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    mock_doc = _make_project_doc(checkout={
        "user_uid": "dev-other@example.com",
        "user_name": "other",
        "checked_out_at": datetime.now(UTC).isoformat(),
        "expires_at": future,
    })
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post("/api/projects/proj-1/checkout", headers=AUTH)
    assert response.status_code == 409


@patch("backend.app.routers.projects._db")
def test_checkout_expired_allows_new(mock_db):
    """POST /checkout succeeds if previous checkout expired."""
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    mock_doc = _make_project_doc(checkout={
        "user_uid": "dev-other@example.com",
        "user_name": "other",
        "checked_out_at": (datetime.now(UTC) - timedelta(hours=3)).isoformat(),
        "expires_at": past,
    })
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post("/api/projects/proj-1/checkout", headers=AUTH)
    assert response.status_code == 200


@patch("backend.app.routers.projects._db")
def test_checkin_releases_lock(mock_db):
    """POST /checkin releases the lock."""
    mock_doc = _make_project_doc(checkout={
        "user_uid": "dev-test@example.com",
        "user_name": "test",
        "checked_out_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    })
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post("/api/projects/proj-1/checkin", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["checkout"]["user_uid"] is None


@patch("backend.app.routers.projects._db")
def test_force_release_owner_only(mock_db):
    """POST /force-release works for owner, fails for others."""
    mock_doc = _make_project_doc(owner="dev-test@example.com", checkout={
        "user_uid": "dev-other@example.com",
        "user_name": "other",
        "checked_out_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    })
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    # Owner can force-release
    response = client.post("/api/projects/proj-1/force-release", headers=AUTH)
    assert response.status_code == 200

    # Non-owner cannot
    mock_doc2 = _make_project_doc(owner="dev-someone-else@example.com")
    mock_doc_ref.get.return_value = mock_doc2
    response = client.post("/api/projects/proj-1/force-release", headers=AUTH)
    assert response.status_code == 403

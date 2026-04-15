"""Tests for project endpoints."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer dev-test@example.com"}


def _mock_firestore():
    """Create a mock Firestore setup."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection
    return mock_db, mock_collection


@patch("backend.app.routers.projects._db")
@patch("backend.app.routers.projects.create_project_folder", return_value=None)
def test_create_project(mock_drive, mock_db):
    """POST /api/projects creates a project."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "proj-123"
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        "/api/projects",
        json={"name": "Test Project"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["id"] == "proj-123"
    assert data["status"] == "active"
    mock_doc_ref.set.assert_called_once()


@patch("backend.app.routers.projects._db")
def test_list_projects(mock_db):
    """GET /api/projects lists user's projects."""
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.id = "proj-1"
    mock_doc.to_dict.return_value = {
        "name": "My Project",
        "owner_uid": "dev-test@example.com",
        "status": "active",
        "checkout": {},
        "created_at": now,
        "updated_at": now,
    }
    mock_db.collection.return_value.where.return_value.where.return_value.stream.return_value = [mock_doc]

    response = client.get("/api/projects", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Project"


@patch("backend.app.routers.projects._db")
def test_get_project(mock_db):
    """GET /api/projects/{id} returns a project."""
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.id = "proj-1"
    mock_doc.to_dict.return_value = {
        "name": "My Project",
        "owner_uid": "dev-test@example.com",
        "status": "active",
        "checkout": {},
        "created_at": now,
        "updated_at": now,
    }
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    response = client.get("/api/projects/proj-1", headers=AUTH_HEADER)
    assert response.status_code == 200
    assert response.json()["name"] == "My Project"


@patch("backend.app.routers.projects._db")
def test_get_project_not_found(mock_db):
    """GET /api/projects/{id} returns 404 for missing project."""
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    response = client.get("/api/projects/nonexistent", headers=AUTH_HEADER)
    assert response.status_code == 404


@patch("backend.app.routers.projects._db")
def test_archive_project(mock_db):
    """POST /api/projects/{id}/archive sets status to archived."""
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "name": "My Project",
        "owner_uid": "dev-test@example.com",
        "status": "active",
        "checkout": {},
        "created_at": now,
        "updated_at": now,
    }
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post("/api/projects/proj-1/archive", headers=AUTH_HEADER)
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_projects_requires_auth():
    """Project endpoints require authentication."""
    response = client.get("/api/projects")
    assert response.status_code == 401

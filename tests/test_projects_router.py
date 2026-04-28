"""Tests for Projects router (Sprint B — thin org scope)."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.projects.get_firestore_client"


@patch(PATCH_DB)
def test_create_project_no_default_model(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    proj_doc_ref = MagicMock()
    proj_doc_ref.id = "proj-1"
    mock_client.collection.return_value.document.return_value = proj_doc_ref

    resp = client.post(
        "/api/projects",
        json={"name": "Campus Adele", "code_name": "campus_adele"},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Campus Adele"
    assert data["status"] == "active"
    assert data["default_model_id"] is None


@patch(PATCH_DB)
def test_create_project_with_default_model(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    model_doc = MagicMock()
    model_doc.exists = True
    model_doc.to_dict.return_value = {"name": "M", "version": 2}
    proj_doc_ref = MagicMock()
    proj_doc_ref.id = "proj-2"

    def collection_side_effect(name):
        col = MagicMock()
        if name.endswith("models"):
            col.document.return_value.get.return_value = model_doc
        elif name.endswith("projects"):
            col.document.return_value = proj_doc_ref
        return col

    mock_client.collection.side_effect = collection_side_effect

    resp = client.post(
        "/api/projects",
        json={"name": "X", "default_model_id": "m1"},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["default_model_name"] == "M"
    assert resp.json()["default_model_version"] == 2


@patch(PATCH_DB)
def test_create_project_404_when_default_model_missing(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    model_doc = MagicMock()
    model_doc.exists = False
    mock_client.collection.return_value.document.return_value.get.return_value = model_doc

    resp = client.post(
        "/api/projects",
        json={"name": "X", "default_model_id": "missing"},
        headers=AUTH,
    )
    assert resp.status_code == 404


@patch(PATCH_DB)
def test_list_projects(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    now = datetime.now(UTC)
    proj_doc = MagicMock()
    proj_doc.id = "proj-1"
    proj_doc.to_dict.return_value = {
        "name": "CA", "code_name": "ca",
        "status": "active", "created_at": now,
    }
    mock_client.collection.return_value.stream.return_value = [proj_doc]
    mock_client.collection.return_value.document.return_value.collection.return_value.stream.return_value = []

    resp = client.get("/api/projects", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["pack_count"] == 0

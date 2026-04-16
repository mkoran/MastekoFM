"""Tests for Excel Projects router."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.excel_projects.get_firestore_client"


@patch(PATCH_DB)
def test_create_excel_project(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    # Template doc exists
    tpl_doc = MagicMock()
    tpl_doc.exists = True
    tpl_doc.to_dict.return_value = {"name": "Tpl", "version": 1}
    # Project doc ref
    proj_doc_ref = MagicMock()
    proj_doc_ref.id = "proj-1"

    def collection_side_effect(name):
        col = MagicMock()
        if name.endswith("excel_templates"):
            col.document.return_value.get.return_value = tpl_doc
        elif name.endswith("excel_projects"):
            col.document.return_value = proj_doc_ref
        return col

    mock_client.collection.side_effect = collection_side_effect

    resp = client.post(
        "/api/excel-projects",
        json={"name": "Campus Adele", "code_name": "campus_adele", "template_id": "tpl-1"},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Campus Adele"
    assert data["template_id"] == "tpl-1"
    assert data["status"] == "active"


@patch(PATCH_DB)
def test_create_project_404_when_template_missing(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    tpl_doc = MagicMock()
    tpl_doc.exists = False
    mock_client.collection.return_value.document.return_value.get.return_value = tpl_doc

    resp = client.post(
        "/api/excel-projects",
        json={"name": "X", "template_id": "missing"},
        headers=AUTH,
    )
    assert resp.status_code == 404


@patch(PATCH_DB)
def test_list_excel_projects(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    now = datetime.now(UTC)
    proj_doc = MagicMock()
    proj_doc.id = "proj-1"
    proj_doc.to_dict.return_value = {
        "name": "CA", "code_name": "ca", "template_id": "t1",
        "template_name": "T", "status": "active", "created_at": now,
    }
    mock_client.collection.return_value.stream.return_value = [proj_doc]
    # scenarios subcollection returns empty stream
    mock_client.collection.return_value.document.return_value.collection.return_value.stream.return_value = []

    resp = client.get("/api/excel-projects", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["scenario_count"] == 0

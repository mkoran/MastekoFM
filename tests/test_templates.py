"""Tests for assumption templates."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.templates.get_firestore_client"


@patch(PATCH_DB)
def test_create_template(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "tmpl-1"
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        "/api/templates",
        json={
            "name": "Test Template",
            "description": "A test",
            "key_values": [{"key": "land_cost", "display_name": "Land Cost", "category": "Acquisition", "type": "currency"}],
            "tables": [{"key": "rent_roll", "display_name": "Rent Roll", "category": "Revenue",
                         "columns": [{"name": "unit", "type": "text"}, {"name": "rent", "type": "currency"}]}],
        },
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Template"
    assert len(data["key_values"]) == 1
    assert len(data["tables"]) == 1


@patch(PATCH_DB)
def test_list_templates(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.id = "tmpl-1"
    mock_doc.to_dict.return_value = {
        "name": "Multifamily", "description": "", "key_values": [], "tables": [],
        "created_by": "uid", "created_at": now, "updated_at": now,
    }
    mock_db.collection.return_value.stream.return_value = [mock_doc]

    response = client.get("/api/templates", headers=AUTH)
    assert response.status_code == 200
    assert len(response.json()) == 1


@patch("backend.app.routers.templates.get_firestore_client")
def test_apply_template(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    # Mock template document
    mock_tmpl_doc = MagicMock()
    mock_tmpl_doc.exists = True
    mock_tmpl_doc.to_dict.return_value = {
        "name": "Test",
        "key_values": [{"key": "land_cost", "display_name": "Land Cost", "category": "Acq", "type": "currency"}],
        "tables": [{"key": "rent_roll", "display_name": "Rent Roll", "category": "Rev",
                     "columns": [{"name": "unit", "type": "text"}]}],
    }

    # Mock the chain: collection(templates).document(id).get()
    mock_templates_col = MagicMock()
    mock_templates_col.document.return_value.get.return_value = mock_tmpl_doc

    # Mock the chain: collection(projects).document(pid).collection(assumptions).document()
    mock_assumptions_doc = MagicMock()
    mock_assumptions_doc.id = "new-asmp"
    mock_history = MagicMock()
    mock_assumptions_doc.collection.return_value = mock_history

    mock_assumptions_col = MagicMock()
    mock_assumptions_col.document.return_value = mock_assumptions_doc

    mock_projects_col = MagicMock()
    mock_projects_col.document.return_value.collection.return_value = mock_assumptions_col

    def side_effect(name):
        if "templates" in name:
            return mock_templates_col
        return mock_projects_col

    mock_db.collection.side_effect = side_effect

    response = client.post("/api/projects/proj-1/apply-template/tmpl-1", headers=AUTH)
    assert response.status_code == 201
    data = response.json()
    assert data["count"] == 2  # 1 key-value + 1 table


def test_templates_requires_auth():
    response = client.get("/api/templates")
    assert response.status_code == 401

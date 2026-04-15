"""Tests for datasource CRUD endpoints."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer dev-test@example.com"}
BASE = "/api/projects/proj-1/datasources"
PATCH_DB = "backend.app.routers.datasources.get_firestore_client"


@patch(PATCH_DB)
def test_create_datasource(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "ds-1"
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        BASE,
        json={"name": "Test CSV", "type": "csv", "config": {}},
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test CSV"
    assert data["type"] == "csv"
    assert data["sync_status"] == "idle"


@patch(PATCH_DB)
def test_list_datasources(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.id = "ds-1"
    mock_doc.to_dict.return_value = {
        "name": "Test CSV", "type": "csv", "config": {},
        "field_mappings": [], "sync_status": "idle",
        "created_at": now, "updated_at": now,
    }
    mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_doc]

    response = client.get(BASE, headers=AUTH)
    assert response.status_code == 200
    assert len(response.json()) == 1


@patch(PATCH_DB)
def test_get_datasource(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.id = "ds-1"
    mock_doc.to_dict.return_value = {
        "name": "Test CSV", "type": "csv", "config": {},
        "field_mappings": [], "sync_status": "idle",
        "created_at": now, "updated_at": now,
    }
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

    response = client.get(f"{BASE}/ds-1", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["name"] == "Test CSV"


@patch(PATCH_DB)
def test_get_datasource_not_found(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

    response = client.get(f"{BASE}/nonexistent", headers=AUTH)
    assert response.status_code == 404


@patch(PATCH_DB)
def test_update_datasource_mappings(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "name": "Test CSV", "type": "csv", "config": {},
        "field_mappings": [], "sync_status": "idle",
        "created_at": now, "updated_at": now,
    }
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.put(
        f"{BASE}/ds-1",
        json={"field_mappings": [{"source_field": "amount", "assumption_key": "land_cost"}]},
        headers=AUTH,
    )
    assert response.status_code == 200
    mock_doc_ref.update.assert_called_once()


def test_datasources_requires_auth():
    response = client.get(BASE)
    assert response.status_code == 401

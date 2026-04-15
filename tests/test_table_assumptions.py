"""Tests for table assumptions and row CRUD."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer dev-test@example.com"}
BASE = "/api/projects/proj-1/assumptions"
PATCH_DB = "backend.app.routers.assumptions.get_firestore_client"


@patch(PATCH_DB)
def test_create_table_assumption(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "tbl-1"
    mock_history_ref = MagicMock()
    mock_doc_ref.collection.return_value = mock_history_ref
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        BASE,
        json={
            "key": "rent_roll",
            "display_name": "Rent Roll",
            "category": "Revenue",
            "type": "text",
            "format": "table",
            "columns": [
                {"name": "unit", "type": "text"},
                {"name": "sqft", "type": "number"},
                {"name": "rent", "type": "currency"},
            ],
        },
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["format"] == "table"
    assert len(data["columns"]) == 3
    assert data["value"] is None


@patch(PATCH_DB)
def test_add_rows_to_table(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # Mock the assumption doc
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"format": "table", "version": 1}
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc

    # Mock rows subcollection
    mock_rows_ref = MagicMock()
    mock_rows_ref.order_by.return_value.limit.return_value.stream.return_value = []
    mock_row_doc = MagicMock()
    mock_row_doc.id = "row-1"
    mock_rows_ref.document.return_value = mock_row_doc
    mock_doc_ref.collection.return_value = mock_rows_ref

    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        f"{BASE}/tbl-1/rows",
        json={"rows": [{"unit": "101", "sqft": 850, "rent": 1850}]},
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    assert data[0]["data"]["unit"] == "101"


@patch(PATCH_DB)
def test_list_rows(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"format": "table"}

    mock_row = MagicMock()
    mock_row.id = "row-1"
    mock_row.to_dict.return_value = {"row_index": 0, "data": {"unit": "101", "rent": 1850}}

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_rows_ref = MagicMock()
    mock_rows_ref.order_by.return_value.stream.return_value = [mock_row]
    mock_doc_ref.collection.return_value = mock_rows_ref

    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    response = client.get(f"{BASE}/tbl-1/rows", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["data"]["unit"] == "101"


@patch(PATCH_DB)
def test_list_rows_rejects_key_value(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"format": "key_value"}
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

    response = client.get(f"{BASE}/kv-1/rows", headers=AUTH)
    assert response.status_code == 400

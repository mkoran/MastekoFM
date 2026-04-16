"""Tests for Template Groups and Template Group Values."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.template_groups.get_firestore_client"


@patch(PATCH_DB)
def test_create_template_group(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "tg-1"
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    response = client.post(
        "/api/template-groups",
        json={"name": "Construction-to-Perm", "template_ids": ["tmpl-1", "tmpl-2"]},
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Construction-to-Perm"
    assert len(data["template_ids"]) == 2


@patch(PATCH_DB)
def test_list_template_groups(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.id = "tg-1"
    mock_doc.to_dict.return_value = {
        "name": "Test Group", "description": "", "code_name": "test",
        "template_ids": [], "created_at": now, "updated_at": now,
    }
    mock_db.collection.return_value.stream.return_value = [mock_doc]

    response = client.get("/api/template-groups", headers=AUTH)
    assert response.status_code == 200
    assert len(response.json()) == 1


@patch(PATCH_DB)
def test_create_scenario(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # Mock project doc
    mock_project = MagicMock()
    mock_project.exists = True
    mock_project.to_dict.return_value = {"template_group_id": "tg-1"}

    # Mock TGV doc ref
    mock_tgv_ref = MagicMock()
    mock_tgv_ref.id = "tgv-1"

    # Chain: collection(projects).document(pid).get() -> project
    # Chain: collection(projects).document(pid).collection(tgv).document() -> tgv_ref
    mock_project_doc = MagicMock()
    mock_project_doc.get.return_value = mock_project
    mock_project_doc.collection.return_value.document.return_value = mock_tgv_ref

    mock_db.collection.return_value.document.return_value = mock_project_doc

    response = client.post(
        "/api/projects/proj-1/scenarios",
        json={"name": "Optimistic", "code_name": "optimistic"},
        headers=AUTH,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Optimistic"
    assert data["code_name"] == "optimistic"


@patch(PATCH_DB)
def test_list_scenarios(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    now = datetime.now(UTC)
    mock_doc = MagicMock()
    mock_doc.id = "tgv-1"
    mock_doc.to_dict.return_value = {
        "name": "Base Case", "code_name": "base_case", "version": 1,
        "created_at": now, "updated_at": now,
    }
    mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_doc]

    response = client.get("/api/projects/proj-1/scenarios", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Base Case"


@patch(PATCH_DB)
def test_get_app_settings(mock_get_db):
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    response = client.get("/api/settings", headers=AUTH)
    assert response.status_code == 200


def test_template_groups_requires_auth():
    response = client.get("/api/template-groups")
    assert response.status_code == 401

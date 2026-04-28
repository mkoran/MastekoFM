"""Sprint G1 tests for the Workspaces router."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.workspaces.get_firestore_client"


def _fake_db_with_no_existing_ws():
    mock_client = MagicMock()
    new_doc_ref = MagicMock()
    new_doc_ref.id = "ws-new"

    settings_doc = MagicMock()
    settings_doc.exists = True
    settings_doc.to_dict.return_value = {"drive_root_folder_id": "ROOT"}

    def collection_side(name):
        col = MagicMock()
        if name.endswith("workspaces"):
            col.document.return_value = new_doc_ref
            col.where.return_value.limit.return_value.stream.return_value = []
            col.stream.return_value = []
        elif name.endswith("settings"):
            col.document.return_value.get.return_value = settings_doc
        elif name.endswith("projects"):
            col.where.return_value.stream.return_value = []
        return col

    mock_client.collection.side_effect = collection_side
    return mock_client, new_doc_ref


@patch("backend.app.routers.workspaces.drive_service.ensure_workspace_folders",
       return_value={"workspace": "ws-fold", "models": "m", "output_templates": "t", "projects": "p"})
@patch(PATCH_DB)
def test_create_workspace_records_creator_as_member(mock_db, _drive):
    mock_client, _ = _fake_db_with_no_existing_ws()
    mock_db.return_value = mock_client

    resp = client.post(
        "/api/workspaces",
        json={"name": "Acme Co", "code_name": "acme"},
        headers={**AUTH, "X-MFM-Drive-Token": "tok"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Acme Co"
    assert body["code_name"] == "acme"
    assert body["members"] == ["dev-test@example.com"]
    assert body["member_count"] == 1
    assert body["archived"] is False


@patch("backend.app.routers.workspaces.drive_service.ensure_workspace_folders",
       return_value={"workspace": "ws-fold", "models": "m", "output_templates": "t", "projects": "p"})
@patch(PATCH_DB)
def test_default_workspace_creates_personal_when_none_exists(mock_db, _drive):
    mock_client, new_doc_ref = _fake_db_with_no_existing_ws()
    mock_db.return_value = mock_client

    resp = client.get(
        "/api/workspaces/me/default",
        headers={**AUTH, "X-MFM-Drive-Token": "tok"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Personal"
    assert "dev-test@example.com" in body["members"]


@patch(PATCH_DB)
def test_default_workspace_returns_existing_when_user_is_member(mock_db):
    mock_client = MagicMock()
    existing_doc = MagicMock()
    existing_doc.id = "ws-existing"
    existing_doc.to_dict.return_value = {
        "name": "Existing",
        "code_name": "existing",
        "members": ["dev-test@example.com"],
        "drive_folder_id": "fold-x",
        "created_by": "u-1",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    def collection_side(name):
        col = MagicMock()
        if name.endswith("workspaces"):
            col.where.return_value.limit.return_value.stream.return_value = [existing_doc]
        return col

    mock_client.collection.side_effect = collection_side
    mock_db.return_value = mock_client

    resp = client.get("/api/workspaces/me/default", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["id"] == "ws-existing"


@patch(PATCH_DB)
def test_update_workspace_cannot_remove_all_members(mock_db):
    mock_client = MagicMock()
    ws_doc_ref = MagicMock()
    ws_snap = MagicMock()
    ws_snap.exists = True
    ws_snap.to_dict.return_value = {
        "name": "X",
        "code_name": "x",
        "members": ["u-1"],
        "created_by": "u-1",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    ws_doc_ref.get.return_value = ws_snap

    def collection_side(name):
        col = MagicMock()
        if name.endswith("workspaces"):
            col.document.return_value = ws_doc_ref
        return col

    mock_client.collection.side_effect = collection_side
    mock_db.return_value = mock_client

    resp = client.put(
        "/api/workspaces/ws-1",
        json={"members_remove": ["u-1"]},
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "at least one" in resp.json()["detail"].lower()


def test_workspaces_require_auth():
    assert client.get("/api/workspaces").status_code == 401
    assert client.post("/api/workspaces", json={"name": "x"}).status_code == 401

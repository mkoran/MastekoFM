"""Sprint UX-01-04 smoke tests for Tree Navigator endpoints.

Asserts the routes Sprint A.5 added still respond and return well-shaped JSON.
Does not exercise LibreOffice — the Excel ops are mocked at the
tree_browser.list_input_cells / list_output_cells boundary.
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.tree.get_firestore_client"
PATCH_LOAD_PACK = "backend.app.routers.tree.pack_store.load_pack_bytes_compat"
PATCH_LIST_INPUTS = "backend.app.routers.tree.tree_browser.list_input_cells"
PATCH_LIST_OUTPUTS = "backend.app.routers.tree.tree_browser.list_output_cells"
PATCH_DOWNLOAD_XLSX = "backend.app.routers.tree.storage_service.download_xlsx"


def _fake_pack_doc(exists: bool = True) -> MagicMock:
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = {
        "name": "Hello World Inputs",
        "version": 1,
        "drive_file_id": "drive-abc",
    }
    return doc


@patch(PATCH_LIST_INPUTS, return_value=[
    {"tab": "I_Numbers", "cell_ref": "A1", "value": "a", "type": "text", "label": None},
    {"tab": "I_Numbers", "cell_ref": "B1", "value": 5, "type": "number", "label": "a"},
])
@patch(PATCH_LOAD_PACK, return_value=b"fakebytes")
@patch(PATCH_DB)
def test_list_pack_inputs_returns_cells(mock_db, mock_load, mock_inputs):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    mock_client.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = _fake_pack_doc()

    resp = client.get("/api/projects/proj-1/assumption-packs/pack-1/inputs", headers=AUTH)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pack_id"] == "pack-1"
    assert body["tab_count"] == 1
    assert len(body["cells"]) == 2


@patch(PATCH_LOAD_PACK, return_value=b"fakebytes")
@patch(PATCH_DB)
def test_list_pack_inputs_404_on_missing_pack(mock_db, mock_load):
    mock_client = MagicMock()
    mock_db.return_value = mock_client
    missing = MagicMock()
    missing.exists = False
    mock_client.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = missing

    resp = client.get("/api/projects/proj-1/assumption-packs/missing/inputs", headers=AUTH)
    assert resp.status_code == 404


@patch(PATCH_DB)
def test_list_pack_outputs_no_runs_yet(mock_db):
    """When no completed Run exists, the endpoint returns an empty list with a hint."""
    mock_client = MagicMock()
    mock_db.return_value = mock_client

    proj_doc = MagicMock()
    proj_doc.collection.return_value.document.return_value.get.return_value = _fake_pack_doc()
    mock_client.collection.return_value.document.return_value = proj_doc

    # Runs query returns nothing
    runs_q = MagicMock()
    runs_q.where.return_value = runs_q
    runs_q.order_by.return_value = runs_q
    runs_q.limit.return_value = runs_q
    runs_q.stream.return_value = []

    def collection_side_effect(name):
        if name.endswith("runs"):
            return runs_q
        col = MagicMock()
        col.document.return_value = proj_doc
        return col

    mock_client.collection.side_effect = collection_side_effect

    resp = client.get("/api/projects/proj-1/assumption-packs/pack-1/outputs", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cells"] == []
    assert "No successful runs" in body["hint"]


@patch(PATCH_LIST_OUTPUTS, return_value=[
    {"tab": "O_Results", "cell_ref": "A1", "value": "sum", "type": "text", "label": None},
    {"tab": "O_Results", "cell_ref": "B1", "value": 12, "type": "number", "label": "sum"},
])
@patch(PATCH_DOWNLOAD_XLSX, return_value=b"out-bytes")
@patch(PATCH_DB)
def test_list_pack_outputs_with_completed_run(mock_db, mock_dl, mock_outputs):
    mock_client = MagicMock()
    mock_db.return_value = mock_client

    proj_doc = MagicMock()
    proj_doc.collection.return_value.document.return_value.get.return_value = _fake_pack_doc()

    run_doc = MagicMock()
    run_doc.id = "run-1"
    run_doc.to_dict.return_value = {
        "output_storage_path": "runs/run-1/out.xlsx",
        "started_at": datetime.now(UTC),
        "model_id": "m-1",
        "model_version": 1,
        "output_template_id": "t-1",
        "output_template_version": 1,
    }
    runs_q = MagicMock()
    runs_q.where.return_value = runs_q
    runs_q.order_by.return_value = runs_q
    runs_q.limit.return_value = runs_q
    runs_q.stream.return_value = [run_doc]

    def collection_side_effect(name):
        if name.endswith("runs"):
            return runs_q
        col = MagicMock()
        col.document.return_value = proj_doc
        return col

    mock_client.collection.side_effect = collection_side_effect

    resp = client.get("/api/projects/proj-1/assumption-packs/pack-1/outputs", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-1"
    assert body["tab_count"] == 1
    assert len(body["cells"]) == 2
    assert any(c["value"] == 12 for c in body["cells"])

"""Sprint UX-01-03 smoke tests for /api/runs (three-way composition).

Mocks the heavy Excel/LibreOffice work so this stays a fast unit-style test.
The real end-to-end Hello World assertion (Sum=12 etc.) lives in the engine
tests; these focus on the router shape, validation, and persistence path.
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.runs.get_firestore_client"
PATCH_VALIDATE = "backend.app.routers.runs.run_validator.validate_run_composition"
PATCH_LOAD_MODEL = "backend.app.routers.runs.pack_store.load_model_bytes_compat"
PATCH_LOAD_PACK = "backend.app.routers.runs.pack_store.load_pack_bytes_compat"
PATCH_LOAD_TPL = "backend.app.routers.runs.pack_store.load_output_template_bytes_compat"
PATCH_EXEC = "backend.app.routers.runs.run_executor.execute_run_sync"
PATCH_UPLOAD = "backend.app.routers.runs.storage_service.upload_xlsx"


def _doc(data: dict) -> MagicMock:
    d = MagicMock()
    d.exists = True
    d.to_dict.return_value = data
    return d


def _wire_db(mock_db):
    mock_client = MagicMock()
    mock_db.return_value = mock_client

    proj = _doc({
        "name": "Hello World",
        "code_name": "helloworld",
        "default_model_id": "m1",
    })
    model = _doc({
        "name": "Hello World Model",
        "code_name": "helloworld_model",
        "version": 1,
        "input_tabs": ["I_Numbers"],
        "output_tabs": ["O_Results"],
        "calc_tabs": ["Calc"],
        "drive_file_id": "drive-model-id",
    })
    pack = _doc({
        "name": "Hello World Inputs",
        "code_name": "helloworld_inputs",
        "version": 1,
        "input_tabs": ["I_Numbers"],
        "drive_file_id": "drive-pack-id",
    })
    tpl = _doc({
        "name": "Hello World Report",
        "code_name": "helloworld_report",
        "version": 1,
        "format": "xlsx",
        "m_tabs": ["M_Results"],
        "output_tabs": ["O_Report"],
        "calc_tabs": [],
        "drive_file_id": "drive-tpl-id",
    })

    new_run_ref = MagicMock()
    new_run_ref.id = "run-new-1"
    runs_q = MagicMock()
    runs_q.where.return_value = runs_q
    runs_q.order_by.return_value = runs_q
    runs_q.limit.return_value = runs_q
    runs_q.stream.return_value = []

    def collection_side_effect(name):
        col = MagicMock()
        if name.endswith("runs"):
            col.document.return_value = new_run_ref
            col.where.return_value = runs_q
            col.order_by.return_value = runs_q
        elif name.endswith("models"):
            col.document.return_value.get.return_value = model
        elif name.endswith("output_templates"):
            col.document.return_value.get.return_value = tpl
        elif name.endswith("projects"):
            proj_doc_obj = MagicMock()
            proj_doc_obj.get.return_value = proj
            sub = MagicMock()
            sub.document.return_value.get.return_value = pack
            proj_doc_obj.collection.return_value = sub
            col.document.return_value = proj_doc_obj
        elif name.endswith("settings"):
            sd = MagicMock()
            sd.exists = False
            col.document.return_value.get.return_value = sd
        return col

    mock_client.collection.side_effect = collection_side_effect


@patch(PATCH_UPLOAD, return_value="https://example/run-out.xlsx")
@patch(PATCH_EXEC, return_value={"output_bytes": b"ok", "warnings": []})
@patch(PATCH_LOAD_TPL, return_value=b"tpl")
@patch(PATCH_LOAD_PACK, return_value=b"pack")
@patch(PATCH_LOAD_MODEL, return_value=b"model")
@patch(PATCH_VALIDATE, return_value=[])
@patch(PATCH_DB)
def test_create_run_happy_path(mock_db, *_):
    _wire_db(mock_db)
    resp = client.post(
        "/api/runs",
        json={
            "project_id": "proj-1",
            "model_id": "m1",
            "assumption_pack_id": "pack-1",
            "output_template_id": "tpl-1",
        },
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["output_download_url"] == "https://example/run-out.xlsx"
    assert body["model_version"] == 1
    assert body["assumption_pack_version"] == 1
    assert body["output_template_version"] == 1
    # UX-01-07: triggered_by_email must be persisted
    assert body["triggered_by_email"] == "test@example.com"


@patch(PATCH_VALIDATE, return_value=["I_Foo missing in pack"])
@patch(PATCH_DB)
def test_create_run_400_when_validation_fails(mock_db, _v):
    _wire_db(mock_db)
    resp = client.post(
        "/api/runs",
        json={
            "project_id": "proj-1",
            "model_id": "m1",
            "assumption_pack_id": "pack-1",
            "output_template_id": "tpl-1",
        },
        headers=AUTH,
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "errors" in body["detail"]


@patch(PATCH_DB)
def test_list_runs_filters_by_user_email(mock_db):
    """UX-01-14: GET /api/runs?triggered_by_email=... must filter at the DB layer."""
    mock_client = MagicMock()
    mock_db.return_value = mock_client

    captured: dict = {}
    q = MagicMock()
    def where_side_effect(field, op, value):
        captured.setdefault(field, value)
        return q
    q.where.side_effect = where_side_effect
    q.order_by.return_value = q
    q.limit.return_value = q
    sample = MagicMock()
    sample.id = "run-x"
    sample.to_dict.return_value = {
        "project_id": "proj-1",
        "started_at": datetime.now(UTC),
        "status": "completed",
        "triggered_by": "u-marc",
        "triggered_by_email": "marc@example.com",
    }
    q.stream.return_value = [sample]
    mock_client.collection.return_value = q

    resp = client.get("/api/runs?triggered_by_email=marc%40example.com", headers=AUTH)
    assert resp.status_code == 200, resp.text
    assert captured.get("triggered_by_email") == "marc@example.com"
    body = resp.json()
    assert len(body) == 1
    assert body[0]["triggered_by_email"] == "marc@example.com"

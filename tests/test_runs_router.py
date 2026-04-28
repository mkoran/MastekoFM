"""Sprint C tests for /api/runs (now async).

POST /api/runs no longer blocks on execution — it persists a pending Run + dispatches
(Cloud Tasks if configured, in-thread otherwise) and returns 202.

These tests exercise:
  - The 202 contract + persisted fields
  - Validation gate still rejects with 400
  - User filter still works on /api/runs
  - The internal Cloud Tasks endpoint is gated by X-CloudTasks-TaskName header
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}
PATCH_DB = "backend.app.routers.runs.get_firestore_client"
PATCH_VALIDATE = "backend.app.routers.runs.run_validator.validate_run_composition"
PATCH_ENQUEUE = "backend.app.routers.runs.run_queue.enqueue_run"
PATCH_THREAD = "backend.app.routers.runs.run_queue.execute_in_thread"


def _doc(data: dict) -> MagicMock:
    d = MagicMock()
    d.exists = True
    d.to_dict.return_value = data
    return d


def _wire_db(mock_db, captured_run_data: dict | None = None):
    """Wire up Firestore mocks. captured_run_data dict (if provided) is
    populated with the Run data the handler tries to persist."""
    mock_client = MagicMock()
    mock_db.return_value = mock_client

    proj = _doc({"name": "Hello World", "code_name": "helloworld"})
    model = _doc({
        "name": "Hello World Model", "code_name": "helloworld_model",
        "version": 1, "input_tabs": ["I_Numbers"], "output_tabs": ["O_Results"],
        "calc_tabs": ["Calc"], "drive_file_id": "drive-model",
    })
    pack = _doc({
        "name": "Hello World Inputs", "code_name": "helloworld_inputs",
        "version": 1, "input_tabs": ["I_Numbers"], "drive_file_id": "drive-pack",
    })
    tpl = _doc({
        "name": "Hello World Report", "code_name": "helloworld_report",
        "version": 1, "format": "xlsx", "m_tabs": ["M_Results"],
        "output_tabs": ["O_Report"], "calc_tabs": [], "drive_file_id": "drive-tpl",
    })

    new_run_ref = MagicMock()
    new_run_ref.id = "run-new-1"
    if captured_run_data is not None:
        new_run_ref.set.side_effect = lambda data: captured_run_data.update(data)

    def collection_side_effect(name):
        col = MagicMock()
        if name.endswith("runs"):
            col.document.return_value = new_run_ref
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
        return col

    mock_client.collection.side_effect = collection_side_effect


@patch(PATCH_THREAD)
@patch(PATCH_ENQUEUE, return_value=None)  # sync mode
@patch(PATCH_VALIDATE, return_value=[])
@patch(PATCH_DB)
def test_create_run_returns_202_pending_in_sync_mode(mock_db, _v, mock_enqueue, mock_thread):
    captured = {}
    _wire_db(mock_db, captured_run_data=captured)

    resp = client.post(
        "/api/runs",
        json={
            "project_id": "proj-1",
            "model_id": "m1",
            "assumption_pack_id": "pack-1",
            "output_template_id": "tpl-1",
        },
        headers={**AUTH, "X-MFM-Drive-Token": "tok-abc"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["model_version"] == 1
    assert body["attempts"] == 0
    assert body["triggered_by_email"] == "test@example.com"

    # The Drive token must be persisted on the Run doc so the worker can read
    # Drive-backed files even though it runs in another process / thread.
    assert captured.get("drive_token") == "tok-abc"

    # Sync mode: in-thread launcher called, Cloud Tasks not used.
    mock_enqueue.assert_called_once()
    mock_thread.assert_called_once()


@patch(PATCH_THREAD)
@patch(PATCH_ENQUEUE, return_value="projects/x/locations/y/queues/q/tasks/t")
@patch(PATCH_VALIDATE, return_value=[])
@patch(PATCH_DB)
def test_create_run_uses_cloud_tasks_when_configured(mock_db, _v, mock_enqueue, mock_thread):
    _wire_db(mock_db)

    resp = client.post(
        "/api/runs",
        json={
            "project_id": "proj-1", "model_id": "m1",
            "assumption_pack_id": "pack-1", "output_template_id": "tpl-1",
        },
        headers=AUTH,
    )
    assert resp.status_code == 202

    mock_enqueue.assert_called_once()
    mock_thread.assert_not_called()  # async mode — no in-thread fallback


@patch(PATCH_VALIDATE, return_value=["I_Foo missing in pack"])
@patch(PATCH_DB)
def test_create_run_400_when_validation_fails(mock_db, _v):
    _wire_db(mock_db)
    resp = client.post(
        "/api/runs",
        json={
            "project_id": "proj-1", "model_id": "m1",
            "assumption_pack_id": "pack-1", "output_template_id": "tpl-1",
        },
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "errors" in resp.json()["detail"]


@patch(PATCH_DB)
def test_list_runs_filters_by_user_email(mock_db):
    """UX-01-14 still works: GET /api/runs?triggered_by_email=... filters at DB."""
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


# ── Internal worker endpoint gating ──────────────────────────────────────────


def test_internal_endpoint_rejects_request_without_cloud_tasks_header():
    """Browsers / curl callers hit 401: missing X-CloudTasks-TaskName header."""
    resp = client.post("/internal/tasks/run/run-x", json={})
    assert resp.status_code == 401
    assert "X-CloudTasks-TaskName" in resp.json()["detail"]


@patch("backend.app.routers.runs._run_worker.execute_run_by_id")
def test_internal_endpoint_calls_worker_when_header_present(mock_exec):
    """With X-CloudTasks-TaskName + DEV_AUTH_BYPASS, the endpoint invokes the worker."""
    mock_exec.return_value = {"status": "completed"}
    resp = client.post(
        "/internal/tasks/run/run-x",
        headers={"X-CloudTasks-TaskName": "fake-task"},
        json={"run_id": "run-x", "drive_token": "tok"},
    )
    assert resp.status_code == 200, resp.text
    mock_exec.assert_called_once_with("run-x", drive_token="tok")

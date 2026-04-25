"""Sprint C tests for backend.app.routers._run_worker.execute_run_by_id.

Covers:
  - Idempotency: re-invoking on a terminal run is a no-op
  - Happy path: pending → running → completed; output_download_url set
  - Failure path: pending → running → failed; error message recorded
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.app.routers import _run_worker

PATCH_DB = "backend.app.routers._run_worker.get_firestore_client"
PATCH_LOAD_MODEL = "backend.app.routers._run_worker.pack_store.load_model_bytes_compat"
PATCH_LOAD_PACK = "backend.app.routers._run_worker.pack_store.load_pack_bytes_compat"
PATCH_LOAD_TPL = "backend.app.routers._run_worker.pack_store.load_output_template_bytes_compat"
PATCH_EXEC = "backend.app.routers._run_worker.run_executor.execute_run_sync"
PATCH_UPLOAD = "backend.app.routers._run_worker.storage_service.upload_xlsx"


def _snap(data: dict | None, exists: bool = True) -> MagicMock:
    """Build a Firestore snapshot mock (the result of doc.get())."""
    s = MagicMock()
    s.exists = exists
    s.to_dict.return_value = data if exists else None
    return s


def _doc_ref_with(snap: MagicMock, captured_updates: list | None = None) -> MagicMock:
    """Build a Firestore document-reference mock whose .get() returns `snap`."""
    ref = MagicMock()
    ref.get.return_value = snap
    if captured_updates is not None:
        ref.update.side_effect = lambda d: captured_updates.append(d)
    return ref


def _wire(
    mock_db,
    *,
    initial_run: dict,
    captured_updates: list,
):
    mock_client = MagicMock()
    mock_db.return_value = mock_client

    run_ref = _doc_ref_with(_snap(initial_run), captured_updates)
    proj_ref = _doc_ref_with(_snap({"name": "Hello World", "code_name": "helloworld"}))
    model_ref = _doc_ref_with(_snap({
        "name": "M", "version": 1, "drive_file_id": "drive-model",
        "input_tabs": ["I_Numbers"], "output_tabs": ["O_Results"], "calc_tabs": [],
    }))
    tpl_ref = _doc_ref_with(_snap({
        "name": "T", "code_name": "t", "version": 1, "drive_file_id": "drive-tpl",
        "format": "xlsx", "m_tabs": ["M_Results"], "output_tabs": ["O_Report"], "calc_tabs": [],
    }))
    pack_ref = _doc_ref_with(_snap({
        "name": "P", "code_name": "p", "version": 1, "drive_file_id": "drive-pack",
    }))
    settings_ref = _doc_ref_with(_snap(None, exists=False))

    # Project doc has a sub-collection for assumption_packs
    proj_subcol = MagicMock()
    proj_subcol.document.return_value = pack_ref
    proj_ref.collection.return_value = proj_subcol

    def collection_side_effect(name):
        col = MagicMock()
        if name.endswith("runs"):
            col.document.return_value = run_ref
        elif name.endswith("models"):
            col.document.return_value = model_ref
        elif name.endswith("output_templates"):
            col.document.return_value = tpl_ref
        elif name.endswith("projects"):
            col.document.return_value = proj_ref
        elif name.endswith("settings"):
            col.document.return_value = settings_ref
        return col

    mock_client.collection.side_effect = collection_side_effect


@patch(PATCH_DB)
def test_idempotent_skip_when_already_completed(mock_db):
    """Cloud Tasks may retry — already-terminal runs must not re-execute."""
    initial = {"status": "completed", "project_id": "p", "model_id": "m",
               "assumption_pack_id": "pa", "output_template_id": "t"}
    updates = []
    _wire(mock_db, initial_run=initial, captured_updates=updates)

    result = _run_worker.execute_run_by_id("run-x")
    assert result["status"] == "completed"
    assert updates == []  # no writes — skipped


@patch(PATCH_UPLOAD, return_value="https://example/out.xlsx")
@patch(PATCH_EXEC, return_value={"output_bytes": b"o", "warnings": []})
@patch(PATCH_LOAD_TPL, return_value=b"t")
@patch(PATCH_LOAD_PACK, return_value=b"p")
@patch(PATCH_LOAD_MODEL, return_value=b"m")
@patch(PATCH_DB)
def test_happy_path_runs_executor_and_writes_completed(mock_db, *_):
    initial = {
        "status": "pending",
        "project_id": "p", "model_id": "m",
        "assumption_pack_id": "pa", "output_template_id": "t",
        "started_at": datetime.now(UTC),
    }
    updates = []
    _wire(mock_db, initial_run=initial, captured_updates=updates)

    result = _run_worker.execute_run_by_id("run-x", drive_token=None)
    assert result["status"] == "completed"
    assert result["output_download_url"] == "https://example/out.xlsx"
    # First update marks running (with attempts=1), second marks completed.
    statuses = [u.get("status") for u in updates if "status" in u]
    assert statuses == ["running", "completed"]
    assert updates[0]["attempts"] == 1
    # Drive token cleared on terminal status (no longer needed).
    assert updates[-1]["drive_token"] is None


@patch(PATCH_LOAD_MODEL, side_effect=RuntimeError("storage broken"))
@patch(PATCH_DB)
def test_failure_path_marks_failed_and_records_error(mock_db, _load):
    initial = {
        "status": "pending",
        "project_id": "p", "model_id": "m",
        "assumption_pack_id": "pa", "output_template_id": "t",
        "started_at": datetime.now(UTC),
    }
    updates = []
    _wire(mock_db, initial_run=initial, captured_updates=updates)

    with pytest.raises(RuntimeError):
        _run_worker.execute_run_by_id("run-x")

    # First update marks running, second marks failed with the error message.
    final = updates[-1]
    assert final["status"] == "failed"
    assert "storage broken" in final["error"]

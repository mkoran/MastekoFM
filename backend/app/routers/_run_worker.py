"""Sprint C — Run worker: idempotent pure execution given a run_id.

This is the function Cloud Tasks (or the sync-thread fallback) calls. It:
  1. Loads the Run doc from Firestore
  2. Returns early if the Run is already terminal (idempotent — Cloud Tasks
     may retry the same task)
  3. Loads Model / Pack / OutputTemplate bytes
  4. Calls run_executor.execute_run_sync()
  5. Uploads output to GCS (and Drive if a drive_token is available)
  6. Updates the Run doc to terminal status

Separated from routers/runs.py so it can be invoked from THREE places:
  - The sync /api/runs path (in-thread for local dev / no Cloud Tasks)
  - The Cloud Tasks worker endpoint /internal/tasks/run/{id}
  - Tests that want to exercise the full pipeline by run_id
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from backend.app.config import get_firestore_client, settings
from backend.app.services import (
    drive_service,
    pack_store,
    run_executor,
    storage_service,
)
from backend.app.services import (
    secrets as secrets_svc,
)

logger = logging.getLogger(__name__)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _runs_ref():
    return get_firestore_client().collection(f"{settings.firestore_collection_prefix}runs")


def _doc(collection: str, doc_id: str) -> dict[str, Any] | None:
    db = get_firestore_client()
    snap = db.collection(f"{settings.firestore_collection_prefix}{collection}").document(doc_id).get()
    return snap.to_dict() if snap.exists else None


def _project_doc(project_id: str) -> dict[str, Any] | None:
    return _doc("projects", project_id)


def _model_doc(model_id: str) -> dict[str, Any] | None:
    return _doc("models", model_id)


def _output_template_doc(tpl_id: str) -> dict[str, Any] | None:
    return _doc("output_templates", tpl_id)


def _pack_doc(project_id: str, pack_id: str) -> dict[str, Any] | None:
    db = get_firestore_client()
    snap = (
        db.collection(f"{settings.firestore_collection_prefix}projects")
        .document(project_id)
        .collection("assumption_packs")
        .document(pack_id)
        .get()
    )
    return snap.to_dict() if snap.exists else None


def execute_run_by_id(run_id: str, *, drive_token: str | None = None) -> dict[str, Any]:
    """Execute a Run identified by id. Idempotent — safe to call twice.

    Returns the final Run dict. Updates the Firestore doc with status
    transitions: pending → running → (completed | failed).

    drive_token is the user's X-MFM-Drive-Token captured at POST /api/runs
    time. Falls back to the doc's persisted token if not provided (e.g.,
    Cloud Tasks delivers the token in the task body, but a manual replay
    might not have it).
    """
    run_ref = _runs_ref().document(run_id)
    snap = run_ref.get()
    if not snap.exists:
        raise ValueError(f"Run {run_id} not found")

    run_data = snap.to_dict()

    # Idempotency: don't re-execute terminal runs (Cloud Tasks retry safety)
    if run_data.get("status") in TERMINAL_STATUSES:
        logger.info("Run %s already %s — skipping", run_id, run_data["status"])
        return run_data

    # Drive token: prefer caller-supplied (Cloud Tasks delivers fresh from the
    # original POST). Fall back to persisted-on-doc, decrypting if it's the
    # KMS-encrypted form (Sprint F). Plaintext drive_token is legacy / fallback.
    if not drive_token:
        ciphertext = run_data.get("drive_token_encrypted")
        if ciphertext:
            try:
                drive_token = secrets_svc.decrypt(ciphertext)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "KMS decrypt failed for run %s (%s); checking plaintext fallback",
                    run_id, exc,
                )
        if not drive_token:
            drive_token = run_data.get("drive_token")

    project_id = run_data["project_id"]
    pack_id = run_data["assumption_pack_id"]
    model_id = run_data["model_id"]
    tpl_id = run_data["output_template_id"]

    # Mark running + record attempt
    attempts = (run_data.get("attempts") or 0) + 1
    run_ref.update({
        "status": "running",
        "running_at": datetime.now(UTC),
        "attempts": attempts,
        "updated_at": datetime.now(UTC),
    })

    started_at = run_data.get("started_at") or datetime.now(UTC)
    t0 = time.monotonic()
    try:
        proj = _project_doc(project_id) or {}
        model = _model_doc(model_id)
        pack = _pack_doc(project_id, pack_id)
        tpl = _output_template_doc(tpl_id)
        if not (model and pack and tpl):
            raise ValueError(
                f"Composition missing on retry: model={bool(model)} pack={bool(pack)} tpl={bool(tpl)}"
            )

        model_bytes = pack_store.load_model_bytes_compat(model)
        pack_bytes = pack_store.load_pack_bytes_compat(pack, user_token=drive_token)
        tpl_bytes = pack_store.load_output_template_bytes_compat(tpl, user_token=drive_token)

        result = run_executor.execute_run_sync(
            model_bytes=model_bytes,
            pack_bytes=pack_bytes,
            output_template_bytes=tpl_bytes,
            output_template_format=tpl.get("format", "xlsx"),
        )

        project_code = storage_service.safe_name(
            proj.get("code_name") or proj.get("name", ""), fallback=project_id
        )
        pack_code = pack.get("code_name", "pack")
        tpl_code = tpl.get("code_name", "tpl")
        ts = started_at.strftime("%Y%m%d_%H%M%S")
        out_filename = f"{ts}_{project_code}_{pack_code}_{tpl_code}.xlsx"
        out_path = f"runs/{run_id}/{out_filename}"
        download_url = storage_service.upload_xlsx(
            out_path, result["output_bytes"], download_filename=out_filename
        )

        # Best-effort Drive copy
        output_drive_file_id: str | None = None
        if drive_token:
            try:
                root_doc = (
                    get_firestore_client()
                    .collection(f"{settings.firestore_collection_prefix}settings")
                    .document("app")
                    .get()
                    .to_dict()
                    or {}
                )
                root = root_doc.get("drive_root_folder_id") or settings.drive_root_folder_id
                if root:
                    folders = drive_service.ensure_project_folders(
                        root, project_code, user_access_token=drive_token
                    )
                    output_drive_file_id = drive_service.upload_file(
                        folders["outputs"],
                        out_filename,
                        result["output_bytes"],
                        XLSX_MIME,
                        user_access_token=drive_token,
                    )
            except Exception:  # noqa: BLE001 — Drive copy is best-effort
                logger.warning("Drive output copy failed for run %s", run_id, exc_info=True)

        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t0) * 1000)
        updates = {
            "status": "completed",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output_storage_path": out_path,
            "output_download_url": download_url,
            "output_drive_file_id": output_drive_file_id,
            "warnings": result["warnings"],
            "updated_at": completed_at,
            # Drop the persisted Drive token now that we don't need it again.
            "drive_token": None,
            "drive_token_encrypted": None,  # Sprint F
        }
        run_ref.update(updates)
        logger.info("Run %s completed in %dms", run_id, duration_ms)
        return {**run_data, **updates}

    except Exception as exc:  # noqa: BLE001 — fail the run with the message
        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)
        run_ref.update({
            "status": "failed",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": err_msg,
            "updated_at": completed_at,
            # Don't keep token on failed runs either — we won't retry from here.
            "drive_token": None,
            "drive_token_encrypted": None,  # Sprint F
        })
        logger.exception("Run %s failed: %s", run_id, err_msg)
        raise

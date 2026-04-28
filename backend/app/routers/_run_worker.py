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
    excel_engine,
    narrative_pdf_service,
    pack_store,
    run_executor,
    storage_service,
)
from backend.app.services import (
    secrets as secrets_svc,
)

logger = logging.getLogger(__name__)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _runs_ref():
    return get_firestore_client().collection(f"{settings.firestore_collection_prefix}runs")


def _build_artifacts(
    *,
    xlsx_drive_file_id: str | None,
    xlsx_filename: str,
    xlsx_size_bytes: int,
    xlsx_download_url: str | None,
    pdf_drive_file_id: str | None = None,
    pdf_filename: str | None = None,
    pdf_size_bytes: int = 0,
    google_doc_pdf_drive_file_id: str | None = None,
    google_doc_pdf_filename: str | None = None,
    google_doc_pdf_size_bytes: int = 0,
) -> list[dict[str, Any]]:
    """Compose the ``output_artifacts`` list on a Run doc.

    One entry per artifact produced. Today: xlsx (always when Drive OK), PDF
    rendered from xlsx (Sprint D-1, opt-in via ``pdf_export_xlsx``), narrative
    PDF rendered from a Google Doc template (Sprint D-2, opt-in via
    ``google_doc_template_drive_file_id``).
    """
    artifacts: list[dict[str, Any]] = []
    if xlsx_drive_file_id:
        artifacts.append({
            "format": "xlsx",
            "kind": "spreadsheet",
            "filename": xlsx_filename,
            "drive_file_id": xlsx_drive_file_id,
            "download_url": xlsx_download_url,
            "edit_url": f"https://docs.google.com/spreadsheets/d/{xlsx_drive_file_id}/edit",
            "size_bytes": xlsx_size_bytes,
        })
    if pdf_drive_file_id and pdf_filename:
        artifacts.append({
            "format": "pdf",
            "kind": "spreadsheet_pdf",  # Sprint D-1: rendered from the xlsx
            "filename": pdf_filename,
            "drive_file_id": pdf_drive_file_id,
            "download_url": f"https://drive.google.com/uc?id={pdf_drive_file_id}&export=download",
            "edit_url": f"https://drive.google.com/file/d/{pdf_drive_file_id}/view",
            "size_bytes": pdf_size_bytes,
        })
    if google_doc_pdf_drive_file_id and google_doc_pdf_filename:
        artifacts.append({
            "format": "pdf",
            "kind": "narrative_pdf",  # Sprint D-2: from the Google Doc template
            "filename": google_doc_pdf_filename,
            "drive_file_id": google_doc_pdf_drive_file_id,
            "download_url": f"https://drive.google.com/uc?id={google_doc_pdf_drive_file_id}&export=download",
            "edit_url": f"https://drive.google.com/file/d/{google_doc_pdf_drive_file_id}/view",
            "size_bytes": google_doc_pdf_size_bytes,
        })
    return artifacts


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

        model_bytes = pack_store.load_model_bytes_compat(model, user_token=drive_token)
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
        # Sprint G1: outputs go to a PER-RUN Drive folder. Each run owns a
        # folder under {workspace}/Projects/{project}/Runs/{ts}_{pack}_{tpl}/.
        # Multi-format outputs (xlsx today, pdf/docx future) live alongside
        # versioned filenames inside the run folder.
        root_doc = (
            get_firestore_client()
            .collection(f"{settings.firestore_collection_prefix}settings")
            .document("app")
            .get()
            .to_dict()
            or {}
        )
        root = root_doc.get("drive_root_folder_id") or settings.drive_root_folder_id

        # Resolve workspace code (from project's workspace_id)
        ws_code = "default"
        ws_id = proj.get("workspace_id")
        if ws_id:
            ws_snap = (
                get_firestore_client()
                .collection(f"{settings.firestore_collection_prefix}workspaces")
                .document(ws_id)
                .get()
            )
            if ws_snap.exists:
                ws_code = (ws_snap.to_dict() or {}).get("code_name", "default")

        run_folder_name_str = drive_service.run_folder_name(started_at, pack_code, tpl_code)
        # Sprint G3 — output filename per Marc's spec:
        #   {YYYYMMDD_HHMMSS}_{model_code}_V{model_version}_AP{NN}.xlsx
        # e.g. 20260427_224908_helloworld_model_V1_AP01.xlsx
        # The timestamp here uses the started_at on the Run; matches the
        # parent folder's prefix (no leading dash; the folder name uses
        # YYYYMMDD-HHMMSS, the file uses YYYYMMDD_HHMMSS).
        model_code = model.get("code_name") or model.get("name") or "model"
        model_version = model.get("version", 1)
        pack_number = pack.get("pack_number") or 0
        ts_for_file = started_at.strftime("%Y%m%d_%H%M%S")
        out_filename = (
            f"{ts_for_file}_{model_code}_V{model_version}_AP{pack_number:02d}.xlsx"
        )

        output_drive_file_id: str | None = None
        output_folder_id: str | None = None
        download_url: str | None = None
        # Sprint D-1: PDF artifact (rendered from output xlsx via LibreOffice)
        pdf_drive_file_id: str | None = None
        pdf_filename: str | None = None
        pdf_size_bytes: int = 0
        # Sprint D-2: Narrative PDF artifact (rendered from a Google Doc template)
        narrative_pdf_drive_file_id: str | None = None
        narrative_pdf_filename: str | None = None
        narrative_pdf_size_bytes: int = 0

        if root and drive_token:
            try:
                ws_folders = drive_service.ensure_workspace_folders(
                    root, ws_code, user_access_token=drive_token
                )
                proj_folders = drive_service.ensure_project_folder_v2(
                    ws_folders["projects"], project_code, user_access_token=drive_token
                )
                output_folder_id = drive_service.ensure_run_folder(
                    proj_folders["runs"], run_folder_name_str, user_access_token=drive_token
                )
                output_drive_file_id = drive_service.upload_file(
                    output_folder_id, out_filename, result["output_bytes"],
                    XLSX_MIME, user_access_token=drive_token,
                )
                if output_drive_file_id:
                    download_url = (
                        f"https://drive.google.com/uc?id={output_drive_file_id}&export=download"
                    )

                # Sprint D-1 — Option 4: render the output xlsx as PDF and
                # upload it next to the xlsx. Best-effort — a missing or slow
                # LibreOffice never fails the run.
                if tpl.get("pdf_export_xlsx"):
                    try:
                        pdf_bytes = excel_engine.xlsx_to_pdf(result["output_bytes"])
                        if pdf_bytes:
                            pdf_filename = (
                                f"{ts_for_file}_{model_code}_V{model_version}_AP{pack_number:02d}.pdf"
                            )
                            pdf_drive_file_id = drive_service.upload_file(
                                output_folder_id, pdf_filename, pdf_bytes,
                                PDF_MIME, user_access_token=drive_token,
                            )
                            pdf_size_bytes = len(pdf_bytes)
                            logger.info(
                                "Run %s: published PDF (%d bytes, file_id=%s)",
                                run_id, pdf_size_bytes, pdf_drive_file_id,
                            )
                        else:
                            logger.warning("Run %s: xlsx→pdf returned None", run_id)
                    except Exception:  # noqa: BLE001 — PDF is best-effort
                        logger.warning(
                            "Run %s: PDF export failed; xlsx is still available",
                            run_id, exc_info=True,
                        )

                # Sprint D-2 — Option 1: narrative PDF from a Google Doc
                # template (designer-friendly WYSIWYG). Best-effort.
                gdoc_template_id = tpl.get("google_doc_template_drive_file_id")
                if gdoc_template_id:
                    try:
                        run_meta = {
                            "id": run_id,
                            "project_name": proj.get("name", ""),
                            "project_code": project_code,
                            "model_name": model.get("name", ""),
                            "model_code": model_code,
                            "pack_name": pack.get("name", ""),
                            "pack_code": pack_code,
                            "started_at": started_at.isoformat(),
                        }
                        narrative_pdf_bytes = narrative_pdf_service.render_narrative_pdf_from_google_doc(
                            template_doc_id=gdoc_template_id,
                            output_xlsx_bytes=result["output_bytes"],
                            run_meta=run_meta,
                            user_access_token=drive_token,
                        )
                        if narrative_pdf_bytes:
                            narrative_pdf_filename = (
                                f"{ts_for_file}_{model_code}_V{model_version}_AP{pack_number:02d}_narrative.pdf"
                            )
                            narrative_pdf_drive_file_id = drive_service.upload_file(
                                output_folder_id, narrative_pdf_filename, narrative_pdf_bytes,
                                PDF_MIME, user_access_token=drive_token,
                            )
                            narrative_pdf_size_bytes = len(narrative_pdf_bytes)
                            logger.info(
                                "Run %s: published narrative PDF (%d bytes, file_id=%s)",
                                run_id, narrative_pdf_size_bytes, narrative_pdf_drive_file_id,
                            )
                        else:
                            logger.warning("Run %s: narrative PDF returned None", run_id)
                    except Exception:  # noqa: BLE001 — narrative PDF is best-effort
                        logger.warning(
                            "Run %s: narrative PDF failed; xlsx is still available",
                            run_id, exc_info=True,
                        )
            except Exception:  # noqa: BLE001 — Drive ops are best-effort; run still records
                logger.warning(
                    "Drive output upload failed for run %s — output bytes lost",
                    run_id, exc_info=True,
                )

        if not output_drive_file_id:
            # No Drive available (no token / no root) — record a failed-ish state
            # but keep status=completed since the engine succeeded. UI will show
            # "no downloadable output" to make this loud.
            logger.warning(
                "Run %s completed but output bytes were not persisted (no Drive)", run_id
            )

        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t0) * 1000)
        updates = {
            "status": "completed",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output_folder_id": output_folder_id,                                # Sprint G1
            "output_folder_url": drive_service.folder_url(output_folder_id),     # Sprint G1
            "output_filename": out_filename,                                     # Sprint G3
            "output_artifacts": _build_artifacts(
                xlsx_drive_file_id=output_drive_file_id,
                xlsx_filename=out_filename,
                xlsx_size_bytes=len(result["output_bytes"]),
                xlsx_download_url=download_url,
                pdf_drive_file_id=pdf_drive_file_id,
                pdf_filename=pdf_filename,
                pdf_size_bytes=pdf_size_bytes,
                google_doc_pdf_drive_file_id=narrative_pdf_drive_file_id,
                google_doc_pdf_filename=narrative_pdf_filename,
                google_doc_pdf_size_bytes=narrative_pdf_size_bytes,
            ),
            # Legacy fields kept for back-compat (frontends still read these)
            "output_download_url": download_url,
            "output_drive_file_id": output_drive_file_id,
            # Sprint D-1: top-level PDF fields for the RunsPage "📄 PDF" column.
            # Null when no PDF was produced (template flag off, LO not present,
            # or render failure).
            "output_pdf_drive_file_id": pdf_drive_file_id,
            "output_pdf_filename": pdf_filename,
            # Sprint D-2: top-level narrative PDF fields (Google Doc template).
            "output_narrative_pdf_drive_file_id": narrative_pdf_drive_file_id,
            "output_narrative_pdf_filename": narrative_pdf_filename,
            "warnings": result["warnings"],
            "updated_at": completed_at,
            "drive_token": None,
            "drive_token_encrypted": None,
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

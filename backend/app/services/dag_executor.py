"""DAG execution service — inject scenario values into Excel, recalculate, save output."""
import base64
import io
import logging
from datetime import UTC, datetime
from typing import Any

import openpyxl

from backend.app.config import get_firestore_client, settings
from backend.app.services.excel_engine import inject_values, recalculate_with_libreoffice

logger = logging.getLogger(__name__)


def _get_project_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id)


def get_model_file(project_id: str) -> bytes | None:
    """Get the stored .xlsx model file for a project."""
    doc = _get_project_ref(project_id).get()
    if not doc.exists:
        return None
    model_b64 = doc.to_dict().get("model_file_b64")
    return base64.b64decode(model_b64) if model_b64 else None


def get_cell_map_from_scenario(project_id: str, scenario_id: str) -> dict[str, Any]:
    """Get assumption values from a TGV (scenario) mapped to Excel cells."""
    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix

    # Get input mappings from project
    project_data = _get_project_ref(project_id).get().to_dict() or {}
    input_mappings = project_data.get("input_mappings", {})

    # Get scenario values
    tgv_doc = db.collection(f"{prefix}projects").document(project_id).collection("tgv").document(scenario_id).get()
    if not tgv_doc.exists:
        return {}
    tgv = tgv_doc.to_dict()
    values = tgv.get("values", {})

    # Map assumption keys → cell references
    cell_map: dict[str, Any] = {}
    for key, value in values.items():
        if key in input_mappings and value is not None:
            cell_map[input_mappings[key]] = value

    return cell_map


def get_cell_map_from_assumptions(project_id: str) -> dict[str, Any]:
    """Get assumption values from legacy per-project assumptions mapped to cells."""
    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix
    assumptions_ref = db.collection(f"{prefix}projects").document(project_id).collection("assumptions")

    project_data = _get_project_ref(project_id).get().to_dict() or {}
    input_mappings = project_data.get("input_mappings", {})

    cell_map: dict[str, Any] = {}
    for doc in assumptions_ref.where("format", "==", "key_value").stream():
        data = doc.to_dict()
        key = data.get("key", "")
        value = data.get("value")
        if key in input_mappings and value is not None:
            cell_map[input_mappings[key]] = value

    return cell_map


def _get_app_drive_folder() -> str | None:
    """Get the app-level Drive root folder from settings."""
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}settings").document("app").get()
    if doc.exists:
        return doc.to_dict().get("drive_root_folder_id")
    return settings.drive_root_folder_id or None


def run_calculation(project_id: str, scenario_id: str | None = None, google_access_token: str | None = None) -> dict[str, Any]:
    """Run the full calculation pipeline.

    If scenario_id is provided, uses that TGV's values.
    Otherwise falls back to legacy per-project assumptions.

    Output folder: <ProjectCode>/<TGVCode>/YYYYMMDDHHMM_<ProjectCode>_<TGVCode>/
    """
    model_bytes = get_model_file(project_id)
    if not model_bytes:
        return {"success": False, "errors": ["No model file uploaded. Go to DAG → Upload Model."]}

    now = datetime.now(UTC)
    _get_project_ref(project_id).update({"calculation_status": "calculating", "updated_at": now})

    try:
        # Get project info
        project_data = _get_project_ref(project_id).get().to_dict() or {}
        project_name = project_data.get("name", "model")
        project_code = project_data.get("code_name") or project_name.replace(" ", "_")[:20]

        # Get scenario info if provided
        scenario_name = None
        scenario_code = None
        if scenario_id:
            prefix = settings.firestore_collection_prefix
            tgv_doc = get_firestore_client().collection(f"{prefix}projects").document(project_id).collection("tgv").document(scenario_id).get()
            if tgv_doc.exists:
                tgv = tgv_doc.to_dict()
                scenario_name = tgv.get("name", "")
                scenario_code = tgv.get("code_name") or scenario_name.replace(" ", "_")[:20]

        # Get cell map from scenario or legacy assumptions
        if scenario_id:
            cell_map = get_cell_map_from_scenario(project_id, scenario_id)
        else:
            cell_map = get_cell_map_from_assumptions(project_id)

        # Load workbook and inject
        wb = openpyxl.load_workbook(io.BytesIO(model_bytes))
        if cell_map and "Inputs & Assumptions" in wb.sheetnames:
            count = inject_values(wb, "Inputs & Assumptions", cell_map)
            logger.info("Injected %d/%d values", count, len(cell_map))

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()

        # Recalculate
        recalced_bytes = recalculate_with_libreoffice(buf.getvalue())
        final_bytes = recalced_bytes if recalced_bytes else buf.getvalue()

        # Store output for download
        _get_project_ref(project_id).update({
            "output_file_b64": base64.b64encode(final_bytes).decode(),
        })

        # Upload to Google Drive (using user's token) or GCS (fallback)
        from backend.app.services.drive_service import create_project_folder, upload_file

        download_link = None
        drive_link = None
        upload_error = None
        timestamp = now.strftime("%Y%m%d%H%M")

        # Get Drive root folder from app settings
        drive_root = _get_app_drive_folder()

        if google_access_token and drive_root:
            # Upload to Drive using user's credentials
            try:
                # Ensure project folder exists
                drive_folder_id = project_data.get("drive_folder_id")
                if not drive_folder_id:
                    drive_folder_id = create_project_folder(project_name, user_access_token=google_access_token)
                    if drive_folder_id:
                        _get_project_ref(project_id).update({"drive_folder_id": drive_folder_id})

                if drive_folder_id:
                    safe_scenario = (scenario_code or "model").replace(" ", "_")
                    filename = f"{timestamp}_{project_code}_{safe_scenario}.xlsx"
                    file_id = upload_file(
                        drive_folder_id, filename, final_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        user_access_token=google_access_token,
                    )
                    if file_id:
                        drive_link = f"https://drive.google.com/file/d/{file_id}/view"
                        download_link = drive_link
                        logger.info("Uploaded to Drive: %s", drive_link)
            except Exception as e:
                upload_error = f"Drive: {e}"
                logger.warning("Drive upload failed: %s", e)

        # Fallback: upload to GCS
        if not download_link:
            try:
                from google.cloud import storage as gcs

                safe_project = project_code.replace(" ", "_").replace("/", "_")
                safe_scenario = (scenario_code or "model").replace(" ", "_").replace("/", "_")
                blob_name = f"{safe_project}/{safe_scenario}/{timestamp}_{safe_project}_{safe_scenario}.xlsx"

                client = gcs.Client(project=settings.gcp_project)
                bucket = client.bucket("masteko-fm-outputs")
                blob = bucket.blob(blob_name)
                blob.content_disposition = f'attachment; filename="{project_name} - {scenario_name or "Model"}.xlsx"'
                blob.upload_from_string(final_bytes, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                download_link = f"https://storage.googleapis.com/masteko-fm-outputs/{blob_name}"
                logger.info("Uploaded to GCS: %s", download_link)
            except Exception as e2:
                if not upload_error:
                    upload_error = str(e2)
                logger.warning("GCS upload also failed: %s", e2)

        # Update project
        _get_project_ref(project_id).update({
            "calculation_status": "done",
            "last_calculated_at": now,
            "output_download_url": download_link or f"/api/projects/{project_id}/model/download",
            "output_drive_link": download_link,
            "output_filename": f"{project_name} - {scenario_name or 'Model'}.xlsx",
            "calculation_used_libreoffice": recalced_bytes is not None,
            "assumptions_injected": len(cell_map),
            "last_scenario_id": scenario_id,
            "last_scenario_name": scenario_name,
            "updated_at": now,
        })

        return {
            "success": True,
            "nodes_calculated": 1,
            "errors": [upload_error] if upload_error else [],
            "outputs": {
                "download_url": download_link or f"/api/projects/{project_id}/model/download",
                "drive_link": download_link,
                "filename": f"{project_name} - {scenario_name or 'Model'}.xlsx",
                "scenario_name": scenario_name,
                "libreoffice_used": recalced_bytes is not None,
                "assumptions_injected": len(cell_map),
                "file_size_kb": round(len(final_bytes) / 1024, 1),
            },
        }

    except Exception as e:
        logger.exception("Calculation failed for project %s", project_id)
        _get_project_ref(project_id).update({
            "calculation_status": "error",
            "calculation_error": str(e),
            "updated_at": datetime.now(UTC),
        })
        return {"success": False, "errors": [str(e)]}

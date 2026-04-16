"""DAG execution service — inject assumptions into Excel, recalculate, save output."""
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
    data = doc.to_dict()
    model_b64 = data.get("model_file_b64")
    if model_b64:
        return base64.b64decode(model_b64)
    return None


def get_assumptions_as_cell_map(project_id: str) -> dict[str, Any]:
    """Collect all key-value assumptions and map to Excel cell references."""
    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix
    assumptions_ref = db.collection(f"{prefix}projects").document(project_id).collection("assumptions")

    project_doc = _get_project_ref(project_id).get()
    project_data = project_doc.to_dict() if project_doc.exists else {}
    input_mappings = project_data.get("input_mappings", {})

    cell_map: dict[str, Any] = {}
    for doc in assumptions_ref.where("format", "==", "key_value").stream():
        data = doc.to_dict()
        key = data.get("key", "")
        value = data.get("value")
        if key in input_mappings and value is not None:
            cell_map[input_mappings[key]] = value

    return cell_map


def run_calculation(project_id: str) -> dict[str, Any]:
    """Run the full calculation pipeline:

    1. Load the .xlsx template
    2. Inject assumption values into mapped cells
    3. Recalculate with LibreOffice (if available)
    4. Save the completed .xlsx to Google Drive
    5. Return the Drive file link

    The output IS the Excel file — all inputs, formulas, and calculated
    outputs are in the workbook. Users open it in Drive/Excel to see results.
    """
    model_bytes = get_model_file(project_id)
    if not model_bytes:
        return {"success": False, "errors": ["No model file uploaded. Go to DAG → Upload Model."]}

    now = datetime.now(UTC)
    _get_project_ref(project_id).update({"calculation_status": "calculating", "updated_at": now})

    try:
        # Load workbook (preserve formulas for injection)
        wb = openpyxl.load_workbook(io.BytesIO(model_bytes))

        # Inject key-value assumptions
        cell_map = get_assumptions_as_cell_map(project_id)
        if cell_map and "Inputs & Assumptions" in wb.sheetnames:
            count = inject_values(wb, "Inputs & Assumptions", cell_map)
            logger.info("Injected %d/%d assumption values", count, len(cell_map))

        # Save injected workbook
        buf = io.BytesIO()
        wb.save(buf)
        injected_bytes = buf.getvalue()
        wb.close()

        # Recalculate with LibreOffice
        recalced_bytes = recalculate_with_libreoffice(injected_bytes)
        final_bytes = recalced_bytes if recalced_bytes else injected_bytes

        # Get project info for filename
        project_doc = _get_project_ref(project_id).get()
        project_data = project_doc.to_dict() if project_doc.exists else {}
        project_name = project_data.get("name", "model")

        # Upload to Cloud Storage (public bucket for easy download)
        download_link = None
        upload_error = None
        try:
            from google.cloud import storage as gcs

            timestamp = now.strftime("%Y%m%d_%H%M")
            safe_name = project_name.replace(" ", "_").replace("/", "_")
            blob_name = f"{safe_name}/{safe_name}_Model_{timestamp}.xlsx"

            client = gcs.Client(project=settings.gcp_project)
            bucket = client.bucket("masteko-fm-outputs")
            blob = bucket.blob(blob_name)
            blob.content_disposition = f'attachment; filename="{safe_name}_Model_{timestamp}.xlsx"'
            blob.upload_from_string(
                final_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            download_link = f"https://storage.googleapis.com/masteko-fm-outputs/{blob_name}"
            logger.info("Uploaded to GCS: %s", download_link)

            # Also upload as "latest" for easy access
            latest_blob = bucket.blob(f"{safe_name}/latest.xlsx")
            latest_blob.content_disposition = f'attachment; filename="{safe_name}_Latest.xlsx"'
            latest_blob.upload_from_string(
                final_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            upload_error = str(e)
            logger.warning("GCS upload failed: %s", e)

        # Store the output file for download
        _get_project_ref(project_id).update({
            "output_file_b64": base64.b64encode(final_bytes).decode(),
        })

        # Update project with calculation results
        _get_project_ref(project_id).update({
            "calculation_status": "done",
            "last_calculated_at": now,
            "output_download_url": download_link or f"/api/projects/{project_id}/model/download",
            "output_drive_link": download_link,
            "output_filename": f"{project_name} - Model.xlsx",
            "calculation_used_libreoffice": recalced_bytes is not None,
            "assumptions_injected": len(cell_map),
            "updated_at": now,
        })

        return {
            "success": True,
            "nodes_calculated": 1,
            "errors": [upload_error] if upload_error else [],
            "outputs": {
                "download_url": download_link or f"/api/projects/{project_id}/model/download",
                "drive_link": download_link,
                "filename": f"{project_name} - Model.xlsx",
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

"""Spreadsheets router — upload model, configure mappings."""
import base64
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/model", tags=["spreadsheets"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _project_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id)


@router.post("/upload")
async def upload_model(project_id: str, file: UploadFile, current_user: CurrentUser):
    """Upload an .xlsx model file for this project."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be .xlsx")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (10MB max)")

    now = datetime.now(UTC)
    _project_ref(project_id).update({
        "model_file_b64": base64.b64encode(content).decode(),
        "model_filename": file.filename,
        "calculation_status": "idle",
        "updated_at": now,
    })

    return {"message": f"Model '{file.filename}' uploaded ({len(content)} bytes)", "size": len(content)}


@router.get("/status")
async def get_model_status(project_id: str, current_user: CurrentUser):
    """Get the model file and calculation status."""
    doc = _project_ref(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    return {
        "has_model": bool(data.get("model_file_b64")),
        "model_filename": data.get("model_filename"),
        "calculation_status": data.get("calculation_status", "idle"),
        "last_calculated_at": data.get("last_calculated_at"),
        "has_drive_folder": bool(data.get("drive_folder_id")),
        "output_drive_link": data.get("output_drive_link"),
        "output_filename": data.get("output_filename"),
    }


@router.post("/input-mappings")
async def set_input_mappings(project_id: str, mappings: dict[str, str], current_user: CurrentUser):
    """Set the mapping from assumption keys to Excel cell references.

    Body: {"land_purchase_price": "B15", "construction_duration": "B8", ...}
    """
    _project_ref(project_id).update({
        "input_mappings": mappings,
        "updated_at": datetime.now(UTC),
    })
    return {"message": f"Set {len(mappings)} input mappings"}


@router.get("/input-mappings")
async def get_input_mappings(project_id: str, current_user: CurrentUser):
    """Get the current input mappings."""
    doc = _project_ref(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    return doc.to_dict().get("input_mappings", {})


@router.get("/outputs")
async def get_cached_outputs(project_id: str, current_user: CurrentUser):
    """Get the cached calculation outputs."""
    doc = _project_ref(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    data = doc.to_dict()
    return {
        "outputs": data.get("cached_outputs", {}),
        "calculation_status": data.get("calculation_status", "idle"),
        "last_calculated_at": data.get("last_calculated_at"),
    }

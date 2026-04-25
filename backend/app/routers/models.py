"""Excel Templates router — upload + CRUD for .xlsx with I_/O_ tab prefixes."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.model import (
    ModelResponse,
    ModelSummary,
    ModelUpdate,
)
from backend.app.services import excel_template_engine, storage_service

router = APIRouter(tags=["models"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}models")


def _to_response(doc_id: str, data: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        version=data.get("version", 1),
        input_tabs=data.get("input_tabs", []),
        output_tabs=data.get("output_tabs", []),
        calc_tabs=data.get("calc_tabs", []),
        storage_path=data.get("storage_path", ""),
        drive_file_id=data.get("drive_file_id"),
        size_bytes=data.get("size_bytes", 0),
        uploaded_by=data.get("uploaded_by", ""),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


def _to_summary(doc_id: str, data: dict[str, Any]) -> ModelSummary:
    return ModelSummary(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        version=data.get("version", 1),
        input_tab_count=len(data.get("input_tabs", [])),
        output_tab_count=len(data.get("output_tabs", [])),
        calc_tab_count=len(data.get("calc_tabs", [])),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.post("/api/models", response_model=ModelResponse, status_code=201)
async def upload_excel_template(
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
    code_name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
):
    """Upload a new Excel Template. Classifies tabs by I_/O_ prefix and stores in GCS."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (50MB max)")

    try:
        classes = excel_template_engine.classify_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read .xlsx: {exc}") from exc

    if not classes["input_tabs"]:
        raise HTTPException(
            status_code=400,
            detail="Template must contain at least one I_ tab (case-sensitive prefix).",
        )

    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(code_name or name, fallback=doc_ref.id)
    storage_path = f"excel_templates/{doc_ref.id}/v1_{storage_service.safe_name(file.filename or 'template.xlsx')}"
    storage_service.upload_xlsx(storage_path, content, download_filename=file.filename or f"{safe_code}.xlsx")

    now = datetime.now(UTC)
    data = {
        "name": name,
        "code_name": safe_code,
        "description": description,
        "version": 1,
        "input_tabs": classes["input_tabs"],
        "output_tabs": classes["output_tabs"],
        "calc_tabs": classes["calc_tabs"],
        "storage_path": storage_path,
        "drive_file_id": None,
        "size_bytes": len(content),
        "uploaded_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/models", response_model=list[ModelSummary])
async def list_excel_templates(current_user: CurrentUser):
    """List all Excel Templates (summary view)."""
    return [_to_summary(doc.id, doc.to_dict()) for doc in _ref().stream()]


@router.get("/api/models/{template_id}", response_model=ModelResponse)
async def get_excel_template(template_id: str, current_user: CurrentUser):
    """Get one Excel Template."""
    doc = _ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    return _to_response(doc.id, doc.to_dict())


@router.get("/api/models/{template_id}/download")
async def download_excel_template(template_id: str, current_user: CurrentUser):
    """Redirect-ready download URL for the Template .xlsx."""
    doc = _ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    data = doc.to_dict()
    return {"download_url": storage_service.public_url(data.get("storage_path", ""))}


@router.post("/api/models/{template_id}/replace", response_model=ModelResponse)
async def replace_excel_template(
    template_id: str,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
):
    """Replace an existing Template by uploading a new .xlsx.

    Option A per design: the new file's I_/O_/calc tabs become the Template's
    tabs. A diff report is returned so callers can warn users. Projects pinned
    to the old version are NOT automatically upgraded.
    """
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    existing = doc.to_dict()

    new_content = await file.read()
    if not new_content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        existing_content = storage_service.download_xlsx(existing.get("storage_path", ""))
        _, report = excel_template_engine.replace_template_tabs(existing_content, new_content)
        classes = excel_template_engine.classify_bytes(new_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process new file: {exc}") from exc

    new_version = existing.get("version", 1) + 1
    new_path = f"excel_templates/{template_id}/v{new_version}_{storage_service.safe_name(file.filename or 'template.xlsx')}"
    storage_service.upload_xlsx(new_path, new_content, download_filename=file.filename)

    updates = {
        "version": new_version,
        "input_tabs": classes["input_tabs"],
        "output_tabs": classes["output_tabs"],
        "calc_tabs": classes["calc_tabs"],
        "storage_path": new_path,
        "size_bytes": len(new_content),
        "updated_at": datetime.now(UTC),
        "last_replace_report": report,
        "last_replaced_by": current_user["uid"],
    }
    doc_ref.update(updates)
    return _to_response(template_id, {**existing, **updates})


@router.put("/api/models/{template_id}", response_model=ModelResponse)
async def update_excel_template(
    template_id: str, body: ModelUpdate, current_user: CurrentUser
):
    """Update Template metadata (name / description / code_name)."""
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.code_name is not None:
        updates["code_name"] = storage_service.safe_name(body.code_name)
    doc_ref.update(updates)
    return _to_response(template_id, {**doc.to_dict(), **updates})


@router.delete("/api/models/{template_id}", status_code=204)
async def delete_excel_template(template_id: str, current_user: CurrentUser):
    """Delete an Excel Template. Does NOT cascade into projects (they stay pinned)."""
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    # Best-effort blob cleanup; firestore doc is the source of truth
    data = doc.to_dict()
    if data.get("storage_path"):
        storage_service.delete_blob(data["storage_path"])
    doc_ref.delete()

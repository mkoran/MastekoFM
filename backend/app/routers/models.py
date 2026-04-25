"""Excel Templates router — upload + CRUD for .xlsx with I_/O_ tab prefixes.

Sprint UX-01: adds archive/unarchive endpoints, drive_url derivation for the
Models page UX, and PUT support for swapping the underlying drive_file_id
(UX-01-16).
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.model import (
    ModelResponse,
    ModelSummary,
    ModelUpdate,
)
from backend.app.services import drive_service, excel_template_engine, storage_service

router = APIRouter(tags=["models"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}models")


def _drive_url(data: dict[str, Any]) -> str | None:
    """Sprint UX-01: open-in-Sheets URL for Drive-backed Models, or GCS public URL."""
    fid = data.get("drive_file_id")
    if fid:
        return f"https://docs.google.com/spreadsheets/d/{fid}/edit"
    sp = data.get("storage_path")
    if sp:
        return storage_service.public_url(sp)
    return None


def _is_archived(data: dict[str, Any]) -> bool:
    return bool(data.get("archived")) or data.get("status") == "archived"


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
        drive_url=_drive_url(data),
        size_bytes=data.get("size_bytes", 0),
        archived=_is_archived(data),
        uploaded_by=data.get("uploaded_by", ""),
        uploaded_by_email=data.get("uploaded_by_email") or data.get("created_by_email"),
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
        archived=_is_archived(data),
        drive_url=_drive_url(data),
        created_by_email=data.get("uploaded_by_email") or data.get("created_by_email"),
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
        "archived": False,
        "uploaded_by": current_user["uid"],
        "uploaded_by_email": current_user.get("email", ""),
        "created_by_email": current_user.get("email", ""),
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/models", response_model=list[ModelSummary])
async def list_excel_templates(
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
):
    """List all Excel Templates (summary view). Hides archived by default (UX-01)."""
    out: list[ModelSummary] = []
    for doc in _ref().stream():
        data = doc.to_dict()
        if not include_archived and _is_archived(data):
            continue
        out.append(_to_summary(doc.id, data))
    return out


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
    """Update Template metadata (name / description / code_name / drive_file_id / archived).

    Sprint UX-01-16: setting `drive_file_id` swaps the underlying Drive file
    (e.g. you uploaded a new version somewhere else). The file is fetched and
    its tab classification is recomputed so I_/O_/calc tab counts stay accurate.
    """
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
    if body.drive_file_id is not None:
        new_fid = body.drive_file_id.strip()
        if not new_fid:
            raise HTTPException(status_code=400, detail="drive_file_id cannot be empty")
        # Fetch file content + reclassify tabs to keep input/output/calc lists accurate.
        try:
            content = drive_service.download_file(new_fid)
            if not content:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Could not download Drive file. Check the id and that the "
                        "service account / signed-in user can read it."
                    ),
                )
            classes = excel_template_engine.classify_bytes(content)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Drive swap failed: {exc}") from exc
        updates["drive_file_id"] = new_fid
        updates["storage_path"] = None
        updates["input_tabs"] = classes["input_tabs"]
        updates["output_tabs"] = classes["output_tabs"]
        updates["calc_tabs"] = classes["calc_tabs"]
        updates["size_bytes"] = len(content)
    if body.archived is not None:
        updates["archived"] = body.archived
        updates["status"] = "archived" if body.archived else "active"
    doc_ref.update(updates)
    return _to_response(template_id, {**doc.to_dict(), **updates})


@router.post("/api/models/{template_id}/archive", response_model=ModelResponse)
async def archive_model(template_id: str, current_user: CurrentUser):
    """Sprint UX-01: archive a Model (non-destructive)."""
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    updates = {"archived": True, "status": "archived", "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(template_id, {**doc.to_dict(), **updates})


@router.post("/api/models/{template_id}/unarchive", response_model=ModelResponse)
async def unarchive_model(template_id: str, current_user: CurrentUser):
    """Sprint UX-01: re-activate an archived Model."""
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Template not found")
    updates = {"archived": False, "status": "active", "updated_at": datetime.now(UTC)}
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

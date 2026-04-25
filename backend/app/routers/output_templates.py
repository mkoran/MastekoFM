"""OutputTemplates router — third entity in three-way composition.

Sprint A: only format=xlsx supported. Sprint D adds pdf, Sprint H adds docx + google_doc.

Storage: Drive only (matches AssumptionPack convention).
"""
import io
from datetime import UTC, datetime
from typing import Annotated, Any

import openpyxl
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.output_template import (
    OutputTemplateResponse,
    OutputTemplateSummary,
    OutputTemplateUpdate,
)
from backend.app.services import drive_service, excel_template_engine, storage_service

router = APIRouter(tags=["output-templates"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}output_templates")


def _settings_doc() -> dict[str, Any]:
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}settings").document("app").get()
    return doc.to_dict() or {} if doc.exists else {}


def _drive_root_id() -> str:
    return _settings_doc().get("drive_root_folder_id") or settings.drive_root_folder_id


def _ensure_template_folder(user_token: str | None) -> str:
    """Return the Drive folder id for OutputTemplates, creating idempotently."""
    root = _drive_root_id()
    if not root:
        raise HTTPException(
            status_code=400,
            detail="No Drive root folder configured. Set one in Settings before uploading OutputTemplates.",
        )
    if not user_token:
        raise HTTPException(
            status_code=400,
            detail="OutputTemplate upload requires a Google Sign-In access token. Sign in with Google.",
        )
    mfm = drive_service.find_or_create_folder("MastekoFM", root, user_token)
    return drive_service.find_or_create_folder("OutputTemplates", mfm, user_token)


def _to_response(doc_id: str, data: dict[str, Any]) -> OutputTemplateResponse:
    drive_id = data.get("drive_file_id")
    edit_url = (
        f"https://docs.google.com/spreadsheets/d/{drive_id}/edit" if drive_id else None
    )
    return OutputTemplateResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        format=data.get("format", "xlsx"),
        version=data.get("version", 1),
        storage_kind=data.get("storage_kind", "drive_xlsx"),
        storage_path=data.get("storage_path"),
        drive_file_id=drive_id,
        edit_url=edit_url,
        m_tabs=data.get("m_tabs", []),
        output_tabs=data.get("output_tabs", []),
        calc_tabs=data.get("calc_tabs", []),
        size_bytes=data.get("size_bytes", 0),
        uploaded_by=data.get("uploaded_by", ""),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


def _to_summary(doc_id: str, data: dict[str, Any]) -> OutputTemplateSummary:
    return OutputTemplateSummary(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        format=data.get("format", "xlsx"),
        version=data.get("version", 1),
        m_tab_count=len(data.get("m_tabs", [])),
        output_tab_count=len(data.get("output_tabs", [])),
        calc_tab_count=len(data.get("calc_tabs", [])),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


# ── Upload / list / get / update / delete ────────────────────────────────────


@router.post("/api/output-templates", response_model=OutputTemplateResponse, status_code=201)
async def upload_output_template(
    current_user: CurrentUser,
    request: Request,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
    code_name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    fmt: Annotated[str, Form(alias="format")] = "xlsx",
):
    """Upload a new OutputTemplate (format=xlsx only in Sprint A)."""
    if fmt != "xlsx":
        raise HTTPException(
            status_code=400,
            detail=f"Format {fmt!r} not supported in Sprint A (only xlsx). PDF/Word/GoogleDoc come in Sprints D/H.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (50MB max)")

    # Validate the .xlsx content
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read .xlsx: {exc}") from exc
    try:
        errors = excel_template_engine.validate_template(
            wb, role=excel_template_engine.ROLE_OUTPUT_TEMPLATE_XLSX
        )
        classes = excel_template_engine.classify_tabs(wb)
    finally:
        wb.close()
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Upload to Drive
    user_token = request.headers.get("X-MFM-Drive-Token")
    folder_id = _ensure_template_folder(user_token)
    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(code_name or name, fallback=doc_ref.id)
    filename = file.filename or f"{safe_code}.xlsx"

    drive_file_id = drive_service.upload_file(
        folder_id, filename, content, XLSX_MIME, user_access_token=user_token
    )
    if not drive_file_id:
        raise HTTPException(status_code=500, detail="Drive upload failed")

    now = datetime.now(UTC)
    data = {
        "name": name,
        "code_name": safe_code,
        "description": description,
        "format": fmt,
        "version": 1,
        "storage_kind": "drive_xlsx",
        "storage_path": None,
        "drive_file_id": drive_file_id,
        "m_tabs": classes["m_tabs"],
        "output_tabs": classes["output_tabs"],
        "calc_tabs": classes["calc_tabs"],
        "size_bytes": len(content),
        "uploaded_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/output-templates", response_model=list[OutputTemplateSummary])
async def list_output_templates(current_user: CurrentUser):
    return [_to_summary(doc.id, doc.to_dict()) for doc in _ref().stream()]


@router.get("/api/output-templates/{template_id}", response_model=OutputTemplateResponse)
async def get_output_template(template_id: str, current_user: CurrentUser):
    doc = _ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="OutputTemplate not found")
    return _to_response(doc.id, doc.to_dict())


@router.put("/api/output-templates/{template_id}", response_model=OutputTemplateResponse)
async def update_output_template(
    template_id: str, body: OutputTemplateUpdate, current_user: CurrentUser
):
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="OutputTemplate not found")
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.code_name is not None:
        updates["code_name"] = storage_service.safe_name(body.code_name)
    doc_ref.update(updates)
    return _to_response(template_id, {**doc.to_dict(), **updates})


@router.delete("/api/output-templates/{template_id}", status_code=204)
async def delete_output_template(template_id: str, current_user: CurrentUser):
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="OutputTemplate not found")
    # Best-effort: leave Drive file intact (user can clean up manually)
    doc_ref.delete()

"""Models router — upload + CRUD for .xlsx with I_/O_ tab prefixes.

Sprint G1: Models live in Drive (was GCS). Each Model has its own folder
under {workspace}/Models/{model_code}/ containing versioned files
{model_code}_v001.xlsx, _v002.xlsx, etc. The "current" version is the
highest-numbered file. Older versions stay accessible via Drive folder
listing — this is what gives users full version history visibility.

Endpoints:
  POST   /api/models                    upload first version (v1) of a new Model
  GET    /api/models                    list (filter by workspace_id, archived)
  GET    /api/models/{id}               detail
  GET    /api/models/{id}/download      latest .xlsx download URL
  POST   /api/models/{id}/replace       upload a new version (bumps to v(N+1))
  PUT    /api/models/{id}               metadata + drive_file_id swap
  POST   /api/models/{id}/archive       archive
  POST   /api/models/{id}/unarchive     unarchive
  DELETE /api/models/{id}               delete
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.model import (
    ModelResponse,
    ModelSummary,
    ModelUpdate,
)
from backend.app.services import drive_service, excel_template_engine, storage_service

router = APIRouter(tags=["models"])
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}models")


def _ws_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}workspaces")


def _settings_doc() -> dict[str, Any]:
    doc = (
        get_firestore_client()
        .collection(f"{settings.firestore_collection_prefix}settings")
        .document("app")
        .get()
    )
    return doc.to_dict() or {} if doc.exists else {}


def _drive_root_id() -> str:
    return _settings_doc().get("drive_root_folder_id") or settings.drive_root_folder_id


def _drive_url(data: dict[str, Any]) -> str | None:
    """Open-in-Sheets URL for the model's canonical (latest) .xlsx."""
    fid = data.get("drive_file_id")
    if fid:
        return f"https://docs.google.com/spreadsheets/d/{fid}/edit"
    return None


def _resolve_workspace(uid: str, requested_ws_id: str | None) -> tuple[str, str]:
    """Sprint G1: pick a workspace for the Model. Returns (id, code_name)."""
    if requested_ws_id:
        snap = _ws_ref().document(requested_ws_id).get()
        if not snap.exists:
            raise HTTPException(status_code=404, detail=f"Workspace {requested_ws_id} not found")
        d = snap.to_dict()
        return requested_ws_id, d.get("code_name", "")
    # Fall back to user's first workspace
    for doc in _ws_ref().where("members", "array_contains", uid).limit(1).stream():
        d = doc.to_dict()
        return doc.id, d.get("code_name", "")
    raise HTTPException(
        status_code=400,
        detail="No workspace available. Create one first via POST /api/workspaces.",
    )


def _is_archived(data: dict[str, Any]) -> bool:
    return bool(data.get("archived")) or data.get("status") == "archived"


def _to_response(doc_id: str, data: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        workspace_id=data.get("workspace_id"),
        version=data.get("version", 1),
        input_tabs=data.get("input_tabs", []),
        output_tabs=data.get("output_tabs", []),
        calc_tabs=data.get("calc_tabs", []),
        storage_path=data.get("storage_path"),
        drive_folder_id=data.get("drive_folder_id"),
        drive_folder_url=drive_service.folder_url(data.get("drive_folder_id")),
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
        workspace_id=data.get("workspace_id"),
        version=data.get("version", 1),
        input_tab_count=len(data.get("input_tabs", [])),
        output_tab_count=len(data.get("output_tabs", [])),
        calc_tab_count=len(data.get("calc_tabs", [])),
        archived=_is_archived(data),
        drive_folder_url=drive_service.folder_url(data.get("drive_folder_id")),
        drive_url=_drive_url(data),
        created_by_email=data.get("uploaded_by_email") or data.get("created_by_email"),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.post("/api/models", response_model=ModelResponse, status_code=201)
async def upload_excel_template(
    current_user: CurrentUser,
    request: Request,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
    code_name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    workspace_id: Annotated[str, Form()] = "",
):
    """Sprint G1: Upload a new Model. Stored at:
        Workspaces/{ws}/Models/{model_code}/{model_code}_v001.xlsx

    A new Model is created at v1. Use POST /api/models/{id}/replace to add
    later versions (which become _v002.xlsx, _v003.xlsx, ...).
    """
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
            detail="Model must contain at least one I_ tab (case-sensitive prefix).",
        )

    user_token = request.headers.get("X-MFM-Drive-Token")
    if not user_token:
        raise HTTPException(
            status_code=400,
            detail="Model upload requires X-MFM-Drive-Token (Google Drive access token).",
        )

    # Sprint G1: resolve workspace + ensure Drive folders
    ws_id, ws_code = _resolve_workspace(current_user["uid"], workspace_id or None)
    root = _drive_root_id()
    if not root:
        raise HTTPException(
            status_code=400,
            detail="No drive_root_folder_id configured. Set one via /api/settings.",
        )

    # Build folder hierarchy + per-Model folder
    ws_folders = drive_service.ensure_workspace_folders(root, ws_code, user_access_token=user_token)
    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(code_name or name, fallback=doc_ref.id)
    model_folder_id = drive_service.ensure_model_folder(
        ws_folders["models"], safe_code, user_access_token=user_token
    )

    # Upload v1 with the canonical filename
    filename = drive_service.versioned_filename(safe_code, 1, ext="xlsx")
    drive_file_id = drive_service.upload_file(
        model_folder_id, filename, content, XLSX_MIME, user_access_token=user_token,
    )
    if not drive_file_id:
        raise HTTPException(status_code=500, detail="Drive upload failed")

    now = datetime.now(UTC)
    data = {
        "name": name,
        "code_name": safe_code,
        "description": description,
        "workspace_id": ws_id,
        "version": 1,
        "input_tabs": classes["input_tabs"],
        "output_tabs": classes["output_tabs"],
        "calc_tabs": classes["calc_tabs"],
        "storage_path": None,                    # GCS legacy field — null for new Models
        "drive_folder_id": model_folder_id,
        "drive_file_id": drive_file_id,
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
    workspace_id: str | None = Query(default=None, description="Sprint G1: filter to a workspace"),
):
    """List Models. Hides archived by default; optionally filter by workspace."""
    out: list[ModelSummary] = []
    q = _ref()
    if workspace_id:
        q = q.where("workspace_id", "==", workspace_id)
    for doc in q.stream():
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
    """Sprint G1: returns the Drive Open-in-Sheets URL for the Model's latest version."""
    doc = _ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Model not found")
    data = doc.to_dict()
    return {
        "download_url": _drive_url(data),
        "drive_folder_url": drive_service.folder_url(data.get("drive_folder_id")),
    }


@router.get("/api/models/{template_id}/revisions")
async def list_model_revisions(
    template_id: str, current_user: CurrentUser, request: Request,
):
    """Sprint G2: list all versioned files in the Model's Drive folder.

    Returns the version history as separate Drive files (`{code}_v001.xlsx`,
    `_v002.xlsx`, etc.) with timestamps, sizes, and direct edit/download URLs.
    Sorted newest version first.
    """
    doc = _ref().document(template_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Model not found")
    data = doc.to_dict()
    folder_id = data.get("drive_folder_id")
    code = data.get("code_name") or template_id
    if not folder_id:
        return {"model_id": template_id, "revisions": [], "note": "Legacy GCS Model — no Drive folder"}
    user_token = request.headers.get("X-MFM-Drive-Token")
    revs = drive_service.list_versioned_files(folder_id, code, user_access_token=user_token)
    return {"model_id": template_id, "code_name": code, "revisions": revs}


@router.post("/api/models/{template_id}/replace", response_model=ModelResponse)
async def replace_excel_template(
    template_id: str,
    current_user: CurrentUser,
    request: Request,
    file: Annotated[UploadFile, File()],
):
    """Sprint G1: upload a new version (v(N+1)) of an existing Model.

    The new file is uploaded to the Model's existing Drive folder as a NEW file
    named `{model_code}_v{N+1:03d}.xlsx`. Older versions stay as `_v001.xlsx`,
    `_v002.xlsx`, etc. — that's the version history Marc wanted. The Model
    doc's drive_file_id is updated to point at the new latest file.
    """
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Model not found")
    existing = doc.to_dict()

    new_content = await file.read()
    if not new_content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        classes = excel_template_engine.classify_bytes(new_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process new file: {exc}") from exc

    user_token = request.headers.get("X-MFM-Drive-Token")
    if not user_token:
        raise HTTPException(
            status_code=400,
            detail="Replace requires X-MFM-Drive-Token (Google Drive access token).",
        )

    folder_id = existing.get("drive_folder_id")
    if not folder_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "This Model is on legacy GCS storage and can't be replaced under the new "
                "layout. Create a new Model — old GCS Models will be migrated separately."
            ),
        )

    new_version = existing.get("version", 1) + 1
    code = existing.get("code_name", template_id)
    filename = drive_service.versioned_filename(code, new_version, ext="xlsx")
    new_drive_file_id = drive_service.upload_file(
        folder_id, filename, new_content, XLSX_MIME, user_access_token=user_token,
    )
    if not new_drive_file_id:
        raise HTTPException(status_code=500, detail="Drive upload of new version failed")

    updates = {
        "version": new_version,
        "input_tabs": classes["input_tabs"],
        "output_tabs": classes["output_tabs"],
        "calc_tabs": classes["calc_tabs"],
        "drive_file_id": new_drive_file_id,
        "storage_path": None,
        "size_bytes": len(new_content),
        "updated_at": datetime.now(UTC),
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
    """Delete a Model record. Does NOT cascade into projects (they stay pinned).

    Sprint G1: only removes the Firestore doc. The Drive folder + files stay
    intact (user can clean up manually in Drive UI). Legacy GCS files (if any)
    are left in place too — orphan cleanup is a separate ops task.
    """
    doc_ref = _ref().document(template_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Model not found")
    doc_ref.delete()

"""Projects router — thin org scope.

Sprint B (post-redesign): Project no longer binds to a single Model. AssumptionPacks
belong to a Project; Runs reference Project + Model + Pack + OutputTemplate
independently. `default_model_id` is just a UX convenience for the New Run modal.
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdate,
)
from backend.app.services import storage_service

router = APIRouter(tags=["projects"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects")


def _model_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}models")


def _ws_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}workspaces")


def _runs_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}runs")


def _resolve_workspace_id(uid: str, requested_ws_id: str | None) -> tuple[str | None, str | None]:
    """Sprint G1: pick the workspace_id for a new project.

    If the caller passed one, validate it exists. Otherwise find the user's
    first workspace (membership). Returns (workspace_id, workspace_name) or
    (None, None) if no workspace is available — back-compat with old projects.
    """
    if requested_ws_id:
        snap = _ws_ref().document(requested_ws_id).get()
        if not snap.exists:
            raise HTTPException(status_code=404, detail=f"Workspace {requested_ws_id} not found")
        d = snap.to_dict()
        return requested_ws_id, d.get("name")
    # Fall back to user's first workspace
    for doc in _ws_ref().where("members", "array_contains", uid).limit(1).stream():
        d = doc.to_dict()
        return doc.id, d.get("name")
    return None, None


def _pack_subref(project_id: str):
    return _ref().document(project_id).collection("assumption_packs")


def _drive_folder_url(folders: dict[str, Any] | None) -> str | None:
    """Build a Drive web URL from cached folder ids."""
    if not folders:
        return None
    fid = folders.get("project") or folders.get("root") or folders.get("inputs")
    return f"https://drive.google.com/drive/folders/{fid}" if fid else None


def _is_archived(data: dict[str, Any]) -> bool:
    """Sprint UX-01: archived if explicit boolean OR legacy status string."""
    return bool(data.get("archived")) or data.get("status") == "archived"


def _to_response(doc_id: str, data: dict[str, Any]) -> ProjectResponse:
    return ProjectResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        workspace_id=data.get("workspace_id"),
        workspace_name=data.get("workspace_name"),
        default_model_id=data.get("default_model_id"),
        default_model_name=data.get("default_model_name"),
        default_model_version=data.get("default_model_version"),
        status=data.get("status", "active"),
        archived=_is_archived(data),
        drive_folder_url=_drive_folder_url(data.get("drive_folders")),
        created_by=data.get("created_by", ""),
        created_by_email=data.get("created_by_email"),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.post("/api/projects", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, current_user: CurrentUser):
    """Create a Project. default_model_id is optional convenience."""
    default_model_name: str | None = None
    default_model_version: int | None = None
    if body.default_model_id:
        m = _model_ref().document(body.default_model_id).get()
        if not m.exists:
            raise HTTPException(status_code=404, detail="default_model_id not found")
        md = m.to_dict()
        default_model_name = md.get("name")
        default_model_version = md.get("version", 1)

    # Sprint G1: resolve workspace
    ws_id, ws_name = _resolve_workspace_id(current_user["uid"], body.workspace_id)

    now = datetime.now(UTC)
    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(body.code_name or body.name, fallback=doc_ref.id)
    data = {
        "name": body.name,
        "code_name": safe_code,
        "description": body.description,
        "workspace_id": ws_id,
        "workspace_name": ws_name,
        "default_model_id": body.default_model_id,
        "default_model_name": default_model_name,
        "default_model_version": default_model_version,
        "status": "active",
        "archived": False,
        "created_by": current_user["uid"],
        "created_by_email": current_user.get("email", ""),
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/projects", response_model=list[ProjectSummary])
async def list_projects(
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
    workspace_id: str | None = Query(default=None, description="Sprint G1: filter to a single workspace"),
):
    """Sprint UX-01: hides archived projects by default; pass ?include_archived=true to see them.
    Sprint G1: optional workspace_id filter.

    Each summary now includes run_count, last_run_at, last_run_status, created_by_email,
    drive_folder_url. Last-run is computed via a single per-project query (acceptable
    until Project counts grow into the hundreds — denormalize then).
    """
    out: list[ProjectSummary] = []
    runs_collection = _runs_ref()
    q = _ref()
    if workspace_id:
        q = q.where("workspace_id", "==", workspace_id)
    for doc in q.stream():
        data = doc.to_dict()
        if not include_archived and _is_archived(data):
            continue
        pack_count = sum(1 for _ in _pack_subref(doc.id).stream())
        # Last-run lookup per project (small N today; denormalize when N grows)
        last_run_at = None
        last_run_status = None
        run_count = 0
        for r in runs_collection.where("project_id", "==", doc.id).stream():
            run_count += 1
            rd = r.to_dict()
            sa = rd.get("started_at")
            if sa is not None and (last_run_at is None or sa > last_run_at):
                last_run_at = sa
                last_run_status = rd.get("status")
        out.append(ProjectSummary(
            id=doc.id,
            name=data.get("name", ""),
            code_name=data.get("code_name", ""),
            workspace_id=data.get("workspace_id"),
            workspace_name=data.get("workspace_name"),
            default_model_id=data.get("default_model_id"),
            default_model_name=data.get("default_model_name"),
            status=data.get("status", "active"),
            archived=_is_archived(data),
            drive_folder_url=_drive_folder_url(data.get("drive_folders")),
            pack_count=pack_count,
            run_count=run_count,
            last_run_at=last_run_at,
            last_run_status=last_run_status,
            created_by=data.get("created_by", ""),
            created_by_email=data.get("created_by_email"),
            created_at=data.get("created_at", datetime.now(UTC)),
        ))
    return out


@router.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: CurrentUser):
    doc = _ref().document(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(doc.id, doc.to_dict())


@router.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate, current_user: CurrentUser):
    doc_ref = _ref().document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.code_name is not None:
        updates["code_name"] = storage_service.safe_name(body.code_name)
    if body.description is not None:
        updates["description"] = body.description
    if body.default_model_id is not None:
        m = _model_ref().document(body.default_model_id).get()
        if not m.exists:
            raise HTTPException(status_code=404, detail="default_model_id not found")
        md = m.to_dict()
        updates["default_model_id"] = body.default_model_id
        updates["default_model_name"] = md.get("name")
        updates["default_model_version"] = md.get("version", 1)
    if body.status is not None:
        if body.status not in ("active", "archived"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'archived'")
        updates["status"] = body.status
        updates["archived"] = body.status == "archived"
    if body.archived is not None:
        updates["archived"] = body.archived
        updates["status"] = "archived" if body.archived else "active"
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})


@router.post("/api/projects/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(project_id: str, current_user: CurrentUser):
    doc_ref = _ref().document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = {"status": "archived", "archived": True, "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})


@router.post("/api/projects/{project_id}/unarchive", response_model=ProjectResponse)
async def unarchive_project(project_id: str, current_user: CurrentUser):
    """Sprint UX-01: re-activate an archived Project."""
    doc_ref = _ref().document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = {"status": "active", "archived": False, "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})

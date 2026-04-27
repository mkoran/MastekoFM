"""Sprint G1 — Workspaces router.

Workspaces sit above Projects. Each workspace has its own Drive folder
containing all of its Models, OutputTemplates, and Projects.

Members are tracked but permissions aren't enforced yet — that's a separate
sprint. Today, any authenticated user can read/write any workspace.

Endpoints:
  POST   /api/workspaces                 create
  GET    /api/workspaces                 list (filters: ?include_archived, ?member=<uid>)
  GET    /api/workspaces/{id}            detail
  PUT    /api/workspaces/{id}            update (name, description, members_add/remove, archived)
  POST   /api/workspaces/{id}/archive    archive (status helper)
  POST   /api/workspaces/{id}/unarchive  unarchive
  GET    /api/workspaces/me/default      get-or-create the calling user's default workspace
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.workspace import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceSummary,
    WorkspaceUpdate,
)
from backend.app.services import drive_service, storage_service

router = APIRouter(tags=["workspaces"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _ref():
    return get_firestore_client().collection(f"{settings.firestore_collection_prefix}workspaces")


def _projects_ref():
    return get_firestore_client().collection(f"{settings.firestore_collection_prefix}projects")


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


def _is_archived(d: dict[str, Any]) -> bool:
    return bool(d.get("archived"))


def _to_response(doc_id: str, data: dict[str, Any]) -> WorkspaceResponse:
    members = data.get("members") or []
    return WorkspaceResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        members=members,
        member_count=len(members),
        drive_folder_id=data.get("drive_folder_id"),
        drive_folder_url=drive_service.folder_url(data.get("drive_folder_id")),
        archived=_is_archived(data),
        created_by=data.get("created_by", ""),
        created_by_email=data.get("created_by_email"),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


def _to_summary(doc_id: str, data: dict[str, Any], project_count: int) -> WorkspaceSummary:
    members = data.get("members") or []
    return WorkspaceSummary(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        member_count=len(members),
        project_count=project_count,
        drive_folder_url=drive_service.folder_url(data.get("drive_folder_id")),
        archived=_is_archived(data),
        created_at=data.get("created_at", datetime.now(UTC)),
    )


def _ensure_drive_folder(code_name: str, user_token: str | None) -> str | None:
    """Best-effort: create the workspace's Drive folder. Returns folder id or None."""
    root = _drive_root_id()
    if not root or not user_token:
        return None
    try:
        folders = drive_service.ensure_workspace_folders(root, code_name, user_access_token=user_token)
        return folders["workspace"]
    except Exception:
        return None


# ── Create / list / get / update ─────────────────────────────────────────────


@router.post("/api/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(body: WorkspaceCreate, request: Request, current_user: CurrentUser):
    user_token = request.headers.get("X-MFM-Drive-Token")
    now = datetime.now(UTC)
    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(body.code_name or body.name, fallback=doc_ref.id)
    drive_folder_id = _ensure_drive_folder(safe_code, user_token)

    data = {
        "name": body.name,
        "code_name": safe_code,
        "description": body.description,
        "members": [current_user["uid"]],  # creator is auto-member
        "drive_folder_id": drive_folder_id,
        "archived": False,
        "created_by": current_user["uid"],
        "created_by_email": current_user.get("email", ""),
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/workspaces", response_model=list[WorkspaceSummary])
async def list_workspaces(
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
    member: str | None = Query(default=None, description="Filter to workspaces this uid is a member of"),
):
    out: list[WorkspaceSummary] = []
    for doc in _ref().stream():
        data = doc.to_dict()
        if not include_archived and _is_archived(data):
            continue
        if member and member not in (data.get("members") or []):
            continue
        # Project count per workspace (small N for now; denormalize later if needed)
        project_count = sum(
            1 for _p in _projects_ref().where("workspace_id", "==", doc.id).stream()
        )
        out.append(_to_summary(doc.id, data, project_count))
    return out


@router.get("/api/workspaces/me/default", response_model=WorkspaceResponse)
async def get_or_create_default_workspace(request: Request, current_user: CurrentUser):
    """Returns the user's first owned workspace, creating "Personal" if none exists.

    Used by the frontend on sign-in to discover the user's workspace context.
    """
    uid = current_user["uid"]
    # Find an existing workspace where the user is a member
    for doc in _ref().where("members", "array_contains", uid).limit(1).stream():
        return _to_response(doc.id, doc.to_dict())

    # Auto-create "Personal" workspace
    user_token = request.headers.get("X-MFM-Drive-Token")
    now = datetime.now(UTC)
    doc_ref = _ref().document()
    code = storage_service.safe_name(f"personal-{uid[:6]}", fallback=doc_ref.id)
    drive_folder_id = _ensure_drive_folder(code, user_token)
    data = {
        "name": "Personal",
        "code_name": code,
        "description": f"Auto-created default workspace for {current_user.get('email', 'user')}",
        "members": [uid],
        "drive_folder_id": drive_folder_id,
        "archived": False,
        "created_by": uid,
        "created_by_email": current_user.get("email", ""),
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/workspaces/{ws_id}", response_model=WorkspaceResponse)
async def get_workspace(ws_id: str, current_user: CurrentUser):
    doc = _ref().document(ws_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_response(doc.id, doc.to_dict())


@router.put("/api/workspaces/{ws_id}", response_model=WorkspaceResponse)
async def update_workspace(ws_id: str, body: WorkspaceUpdate, current_user: CurrentUser):
    doc_ref = _ref().document(ws_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Workspace not found")
    data = snap.to_dict()
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.archived is not None:
        updates["archived"] = body.archived
    if body.members_add or body.members_remove:
        members = set(data.get("members") or [])
        members.update(body.members_add or [])
        for uid in body.members_remove or []:
            members.discard(uid)
        if not members:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove all members — workspace must have at least one",
            )
        updates["members"] = list(members)
    doc_ref.update(updates)
    return _to_response(ws_id, {**data, **updates})


@router.post("/api/workspaces/{ws_id}/archive", response_model=WorkspaceResponse)
async def archive_workspace(ws_id: str, current_user: CurrentUser):
    doc_ref = _ref().document(ws_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Workspace not found")
    updates = {"archived": True, "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(ws_id, {**snap.to_dict(), **updates})


@router.post("/api/workspaces/{ws_id}/unarchive", response_model=WorkspaceResponse)
async def unarchive_workspace(ws_id: str, current_user: CurrentUser):
    doc_ref = _ref().document(ws_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Workspace not found")
    updates = {"archived": False, "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(ws_id, {**snap.to_dict(), **updates})

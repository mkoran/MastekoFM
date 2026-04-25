"""Projects router — thin org scope.

Sprint B (post-redesign): Project no longer binds to a single Model. AssumptionPacks
belong to a Project; Runs reference Project + Model + Pack + OutputTemplate
independently. `default_model_id` is just a UX convenience for the New Run modal.
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

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


def _pack_subref(project_id: str):
    return _ref().document(project_id).collection("assumption_packs")


def _to_response(doc_id: str, data: dict[str, Any]) -> ProjectResponse:
    return ProjectResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        default_model_id=data.get("default_model_id"),
        default_model_name=data.get("default_model_name"),
        default_model_version=data.get("default_model_version"),
        status=data.get("status", "active"),
        created_by=data.get("created_by", ""),
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

    now = datetime.now(UTC)
    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(body.code_name or body.name, fallback=doc_ref.id)
    data = {
        "name": body.name,
        "code_name": safe_code,
        "description": body.description,
        "default_model_id": body.default_model_id,
        "default_model_name": default_model_name,
        "default_model_version": default_model_version,
        "status": "active",
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/projects", response_model=list[ProjectSummary])
async def list_projects(current_user: CurrentUser):
    out: list[ProjectSummary] = []
    for doc in _ref().stream():
        data = doc.to_dict()
        pack_count = sum(1 for _ in _pack_subref(doc.id).stream())
        out.append(ProjectSummary(
            id=doc.id,
            name=data.get("name", ""),
            code_name=data.get("code_name", ""),
            default_model_id=data.get("default_model_id"),
            default_model_name=data.get("default_model_name"),
            status=data.get("status", "active"),
            pack_count=pack_count,
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
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})


@router.post("/api/projects/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(project_id: str, current_user: CurrentUser):
    doc_ref = _ref().document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = {"status": "archived", "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})

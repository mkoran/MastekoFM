"""Excel Projects router — an Excel Project = one Template + many Scenarios."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.excel_project import (
    ExcelProjectCreate,
    ExcelProjectResponse,
    ExcelProjectSummary,
    ExcelProjectUpdate,
)
from backend.app.services import storage_service

router = APIRouter(tags=["excel-projects"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}excel_projects")


def _template_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}excel_templates")


def _scenario_ref(project_id: str):
    return _ref().document(project_id).collection("scenarios")


def _to_response(doc_id: str, data: dict[str, Any]) -> ExcelProjectResponse:
    return ExcelProjectResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        template_id=data.get("template_id", ""),
        template_name=data.get("template_name", ""),
        template_version_pinned=data.get("template_version_pinned", 1),
        status=data.get("status", "active"),
        created_by=data.get("created_by", ""),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.post("/api/excel-projects", response_model=ExcelProjectResponse, status_code=201)
async def create_excel_project(body: ExcelProjectCreate, current_user: CurrentUser):
    """Create an Excel Project bound to one Template."""
    tpl_doc = _template_ref().document(body.template_id).get()
    if not tpl_doc.exists:
        raise HTTPException(status_code=404, detail="Template not found")
    tpl = tpl_doc.to_dict()

    now = datetime.now(UTC)
    doc_ref = _ref().document()
    safe_code = storage_service.safe_name(body.code_name or body.name, fallback=doc_ref.id)
    data = {
        "name": body.name,
        "code_name": safe_code,
        "description": body.description,
        "template_id": body.template_id,
        "template_name": tpl.get("name", ""),
        "template_version_pinned": tpl.get("version", 1),
        "status": "active",
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("/api/excel-projects", response_model=list[ExcelProjectSummary])
async def list_excel_projects(current_user: CurrentUser):
    """List Excel Projects (active + archived)."""
    out: list[ExcelProjectSummary] = []
    for doc in _ref().stream():
        data = doc.to_dict()
        # scenario count via subcollection count (cheap for small N; revisit for scale)
        scenario_count = sum(1 for _ in _scenario_ref(doc.id).stream())
        out.append(ExcelProjectSummary(
            id=doc.id,
            name=data.get("name", ""),
            code_name=data.get("code_name", ""),
            template_id=data.get("template_id", ""),
            template_name=data.get("template_name", ""),
            status=data.get("status", "active"),
            scenario_count=scenario_count,
            created_at=data.get("created_at", datetime.now(UTC)),
        ))
    return out


@router.get("/api/excel-projects/{project_id}", response_model=ExcelProjectResponse)
async def get_excel_project(project_id: str, current_user: CurrentUser):
    """Get a single Excel Project."""
    doc = _ref().document(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Project not found")
    return _to_response(doc.id, doc.to_dict())


@router.put("/api/excel-projects/{project_id}", response_model=ExcelProjectResponse)
async def update_excel_project(
    project_id: str, body: ExcelProjectUpdate, current_user: CurrentUser
):
    """Update Excel Project metadata."""
    doc_ref = _ref().document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Project not found")
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.code_name is not None:
        updates["code_name"] = storage_service.safe_name(body.code_name)
    if body.description is not None:
        updates["description"] = body.description
    if body.status is not None:
        if body.status not in ("active", "archived"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'archived'")
        updates["status"] = body.status
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})


@router.post("/api/excel-projects/{project_id}/archive", response_model=ExcelProjectResponse)
async def archive_excel_project(project_id: str, current_user: CurrentUser):
    """Archive an Excel Project (non-destructive)."""
    doc_ref = _ref().document(project_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Excel Project not found")
    updates = {"status": "archived", "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_response(project_id, {**doc.to_dict(), **updates})

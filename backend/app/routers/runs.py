"""Runs router — three-way composition execution.

Sprint A: synchronous. POST /api/runs blocks until the Run completes (~2s for
Hello World, ~17s for Campus Adele). Sprint C wraps this in Cloud Tasks.

Endpoints:
  POST   /api/runs                                launch a Run (sync for now)
  POST   /api/runs/validate                       check compatibility (no execution)
  GET    /api/runs                                list (filter by project_id, status)
  GET    /api/runs/{run_id}                       detail
  POST   /api/runs/{run_id}/retry                 new run with same composition
  GET    /api/projects/{project_id}/runs          per-project list
"""
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.run import (
    RunCreate,
    RunResponse,
    RunSummary,
    RunValidateRequest,
    RunValidateResponse,
)
from backend.app.services import (
    drive_service,
    pack_store_compat,
    run_executor,
    run_validator,
    storage_service,
)

router = APIRouter(tags=["runs"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _runs_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}runs")


def _model_doc(model_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    # Sprint A: Models still live in `excel_templates` collection (rename in Sprint B)
    doc = get_firestore_client().collection(f"{prefix}excel_templates").document(model_id).get()
    return doc.to_dict() if doc.exists else None


def _output_template_doc(tpl_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}output_templates").document(tpl_id).get()
    return doc.to_dict() if doc.exists else None


def _project_doc(project_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    # Sprint A: Projects still live in `excel_projects` (rename in Sprint B)
    doc = get_firestore_client().collection(f"{prefix}excel_projects").document(project_id).get()
    return doc.to_dict() if doc.exists else None


def _pack_doc(project_id: str, pack_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    # Sprint A: AssumptionPacks still live as Scenarios under excel_projects (rename Sprint B)
    doc = (
        get_firestore_client()
        .collection(f"{prefix}excel_projects")
        .document(project_id)
        .collection("scenarios")
        .document(pack_id)
        .get()
    )
    return doc.to_dict() if doc.exists else None


def _classes_with_m(data: dict[str, Any]) -> dict[str, Any]:
    """Patch a Firestore doc with m_tabs=[] if it predates Sprint A engine extension."""
    return {**data, "m_tabs": data.get("m_tabs", [])}


def _validate_or_404(
    model_id: str, project_id: str, pack_id: str, output_template_id: str
) -> tuple[dict, dict, dict]:
    proj = _project_doc(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    model = _model_doc(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    pack = _pack_doc(project_id, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"AssumptionPack {pack_id} not found")
    tpl = _output_template_doc(output_template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"OutputTemplate {output_template_id} not found")
    return _classes_with_m(model), _classes_with_m(pack), _classes_with_m(tpl)


# ── Compatibility preview ────────────────────────────────────────────────────


@router.post("/api/runs/validate", response_model=RunValidateResponse)
async def validate_run(body: RunValidateRequest, current_user: CurrentUser):
    """Check whether a (model, pack, output_template) tuple is compatible.

    Doesn't require a project context — used by the New Run modal as the user picks.
    """
    model = _model_doc(body.model_id)
    if not model:
        return RunValidateResponse(compatible=False, errors=[f"Model {body.model_id} not found"])
    tpl = _output_template_doc(body.output_template_id)
    if not tpl:
        return RunValidateResponse(
            compatible=False, errors=[f"OutputTemplate {body.output_template_id} not found"]
        )
    # Pack lookup needs a project — search across projects until we find it (cheap for now)
    pack = None
    prefix = settings.firestore_collection_prefix
    for proj_doc in get_firestore_client().collection(f"{prefix}excel_projects").stream():
        candidate = (
            proj_doc.reference.collection("scenarios")
            .document(body.assumption_pack_id)
            .get()
        )
        if candidate.exists:
            pack = candidate.to_dict()
            break
    if not pack:
        return RunValidateResponse(
            compatible=False,
            errors=[f"AssumptionPack {body.assumption_pack_id} not found"],
        )

    errors = run_validator.validate_run_composition(
        _classes_with_m(model), _classes_with_m(pack), _classes_with_m(tpl)
    )
    return RunValidateResponse(compatible=not errors, errors=errors)


# ── Launch ───────────────────────────────────────────────────────────────────


@router.post("/api/runs", response_model=RunResponse, status_code=201)
async def create_run(body: RunCreate, request: Request, current_user: CurrentUser):
    """Launch a Run (synchronous in Sprint A; Sprint C makes async)."""
    model, pack, tpl = _validate_or_404(
        body.model_id, body.project_id, body.assumption_pack_id, body.output_template_id
    )

    errors = run_validator.validate_run_composition(model, pack, tpl)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    user_token = request.headers.get("X-MFM-Drive-Token")
    started_at = datetime.now(UTC)
    t0 = time.monotonic()

    # Create Run doc immediately
    run_ref = _runs_ref().document()
    run_data: dict[str, Any] = {
        "project_id": body.project_id,
        "assumption_pack_id": body.assumption_pack_id,
        "assumption_pack_version": pack.get("version", 1),
        "assumption_pack_drive_revision_id": None,  # Sprint C+ records revisions
        "model_id": body.model_id,
        "model_version": model.get("version", 1),
        "model_drive_revision_id": None,
        "output_template_id": body.output_template_id,
        "output_template_version": tpl.get("version", 1),
        "output_template_drive_revision_id": None,
        "status": "running",
        "started_at": started_at,
        "triggered_by": current_user["uid"],
        "warnings": [],
    }
    run_ref.set(run_data)

    try:
        # Load all three artifacts via their respective stores
        model_bytes = pack_store_compat.load_model_bytes(model)
        pack_bytes = pack_store_compat.load_pack_bytes(pack, user_token=user_token)
        tpl_bytes = pack_store_compat.load_output_template_bytes(tpl, user_token=user_token)

        result = run_executor.execute_run_sync(
            model_bytes=model_bytes,
            pack_bytes=pack_bytes,
            output_template_bytes=tpl_bytes,
            output_template_format=tpl.get("format", "xlsx"),
        )

        # Persist output to GCS for stable URL
        proj = _project_doc(body.project_id) or {}
        project_code = storage_service.safe_name(
            proj.get("code_name") or proj.get("name", ""), fallback=body.project_id
        )
        pack_code = pack.get("code_name", "pack")
        tpl_code = tpl.get("code_name", "tpl")
        ts = started_at.strftime("%Y%m%d_%H%M%S")
        out_filename = f"{ts}_{project_code}_{pack_code}_{tpl_code}.xlsx"
        out_path = f"runs/{run_ref.id}/{out_filename}"
        download_url = storage_service.upload_xlsx(
            out_path, result["output_bytes"], download_filename=out_filename
        )

        # Best-effort Drive upload too (so it shows up in the user's Drive)
        output_drive_file_id: str | None = None
        if user_token:
            try:
                root = (
                    get_firestore_client()
                    .collection(f"{settings.firestore_collection_prefix}settings")
                    .document("app")
                    .get()
                    .to_dict()
                    or {}
                ).get("drive_root_folder_id") or settings.drive_root_folder_id
                if root:
                    folders = drive_service.ensure_project_folders(
                        root, project_code, user_access_token=user_token
                    )
                    output_drive_file_id = drive_service.upload_file(
                        folders["outputs"],
                        out_filename,
                        result["output_bytes"],
                        XLSX_MIME,
                        user_access_token=user_token,
                    )
            except Exception:
                pass  # GCS is authoritative

        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t0) * 1000)
        updates = {
            "status": "completed",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output_storage_path": out_path,
            "output_download_url": download_url,
            "output_drive_file_id": output_drive_file_id,
            "warnings": result["warnings"],
        }
        run_ref.update(updates)
        return _to_response(run_ref.id, {**run_data, **updates})

    except Exception as exc:
        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t0) * 1000)
        err = str(exc)
        run_ref.update(
            {
                "status": "failed",
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": err,
            }
        )
        raise HTTPException(status_code=500, detail=f"Run failed: {err}") from exc


# ── List / detail / retry ────────────────────────────────────────────────────


def _to_response(doc_id: str, data: dict[str, Any]) -> RunResponse:
    return RunResponse(
        id=doc_id,
        project_id=data.get("project_id", ""),
        assumption_pack_id=data.get("assumption_pack_id", ""),
        assumption_pack_version=data.get("assumption_pack_version", 1),
        assumption_pack_drive_revision_id=data.get("assumption_pack_drive_revision_id"),
        model_id=data.get("model_id", ""),
        model_version=data.get("model_version", 1),
        model_drive_revision_id=data.get("model_drive_revision_id"),
        output_template_id=data.get("output_template_id", ""),
        output_template_version=data.get("output_template_version", 1),
        output_template_drive_revision_id=data.get("output_template_drive_revision_id"),
        status=data.get("status", "pending"),
        started_at=data.get("started_at", datetime.now(UTC)),
        completed_at=data.get("completed_at"),
        duration_ms=data.get("duration_ms"),
        output_storage_path=data.get("output_storage_path"),
        output_download_url=data.get("output_download_url"),
        output_drive_file_id=data.get("output_drive_file_id"),
        warnings=data.get("warnings", []),
        error=data.get("error"),
        triggered_by=data.get("triggered_by", ""),
        retry_of=data.get("retry_of"),
    )


def _to_summary(doc_id: str, data: dict[str, Any]) -> RunSummary:
    return RunSummary(
        id=doc_id,
        project_id=data.get("project_id", ""),
        model_id=data.get("model_id", ""),
        assumption_pack_id=data.get("assumption_pack_id", ""),
        output_template_id=data.get("output_template_id", ""),
        status=data.get("status", "pending"),
        started_at=data.get("started_at", datetime.now(UTC)),
        completed_at=data.get("completed_at"),
        duration_ms=data.get("duration_ms"),
        output_download_url=data.get("output_download_url"),
        triggered_by=data.get("triggered_by", ""),
    )


@router.get("/api/runs", response_model=list[RunSummary])
async def list_runs(
    current_user: CurrentUser,
    project_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50),
):
    q = _runs_ref()
    if project_id:
        q = q.where("project_id", "==", project_id)
    if status:
        q = q.where("status", "==", status)
    q = q.order_by("started_at", direction="DESCENDING").limit(limit)
    return [_to_summary(doc.id, doc.to_dict()) for doc in q.stream()]


@router.get("/api/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, current_user: CurrentUser):
    doc = _runs_ref().document(run_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_response(doc.id, doc.to_dict())


@router.post("/api/runs/{run_id}/retry", response_model=RunResponse, status_code=201)
async def retry_run(run_id: str, request: Request, current_user: CurrentUser):
    """Create a new Run with same composition. retry_of points at the original."""
    doc = _runs_ref().document(run_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Run not found")
    src = doc.to_dict()
    body = RunCreate(
        project_id=src["project_id"],
        assumption_pack_id=src["assumption_pack_id"],
        model_id=src["model_id"],
        output_template_id=src["output_template_id"],
    )
    # Re-launch (sync) — copy the create logic but tag retry_of
    response = await create_run(body=body, request=request, current_user=current_user)
    _runs_ref().document(response.id).update({"retry_of": run_id})
    return await get_run(run_id=response.id, current_user=current_user)


@router.get("/api/projects/{project_id}/runs", response_model=list[RunSummary])
async def list_project_runs(project_id: str, current_user: CurrentUser, limit: int = Query(default=50)):
    q = (
        _runs_ref()
        .where("project_id", "==", project_id)
        .order_by("started_at", direction="DESCENDING")
        .limit(limit)
    )
    return [_to_summary(doc.id, doc.to_dict()) for doc in q.stream()]

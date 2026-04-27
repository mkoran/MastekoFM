"""Runs router — three-way composition execution.

Sprint C: POST /api/runs is now async. The handler:
  1. Persists a Run doc with status=pending (+ user's Drive token, if any)
  2. Enqueues a Cloud Tasks task that POSTs /internal/tasks/run/{id}
     OR (if Cloud Tasks isn't configured — local dev / no queue yet) starts
     a background thread that runs the same worker function inline
  3. Returns 202 with the Run shape (status=pending). The frontend polls.

The Cloud Tasks worker endpoint /internal/tasks/run/{id} lives here too,
gated by the cloud_tasks dep (rejects browser callers).

Endpoints:
  POST   /api/runs                                launch a Run (async; returns 202)
  POST   /api/runs/validate                       check compatibility (no execution)
  GET    /api/runs                                list (filter by project_id, user, status)
  GET    /api/runs/{run_id}                       detail (poll target)
  POST   /api/runs/{run_id}/retry                 new run with same composition
  POST   /internal/tasks/run/{run_id}             Cloud Tasks worker (OIDC-only)
  GET    /api/projects/{project_id}/runs          per-project list
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.middleware.cloud_tasks import verify_cloud_tasks_request
from backend.app.models.run import (
    RunCreate,
    RunResponse,
    RunSummary,
    RunValidateRequest,
    RunValidateResponse,
)
from backend.app.routers import _run_worker
from backend.app.services import (
    run_queue,
    run_validator,
)
from backend.app.services import (
    secrets as secrets_svc,
)

router = APIRouter(tags=["runs"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _runs_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}runs")


def _model_doc(model_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}models").document(model_id).get()
    return doc.to_dict() if doc.exists else None


def _output_template_doc(tpl_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}output_templates").document(tpl_id).get()
    return doc.to_dict() if doc.exists else None


def _project_doc(project_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}projects").document(project_id).get()
    return doc.to_dict() if doc.exists else None


def _pack_doc(project_id: str, pack_id: str) -> dict[str, Any] | None:
    prefix = settings.firestore_collection_prefix
    doc = (
        get_firestore_client()
        .collection(f"{prefix}projects")
        .document(project_id)
        .collection("assumption_packs")
        .document(pack_id)
        .get()
    )
    return doc.to_dict() if doc.exists else None


def _classes_with_m(data: dict[str, Any]) -> dict[str, Any]:
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
    """Check whether a (model, pack, output_template) tuple is compatible."""
    model = _model_doc(body.model_id)
    if not model:
        return RunValidateResponse(compatible=False, errors=[f"Model {body.model_id} not found"])
    tpl = _output_template_doc(body.output_template_id)
    if not tpl:
        return RunValidateResponse(
            compatible=False, errors=[f"OutputTemplate {body.output_template_id} not found"]
        )
    pack = None
    prefix = settings.firestore_collection_prefix
    for proj_doc in get_firestore_client().collection(f"{prefix}projects").stream():
        candidate = (
            proj_doc.reference.collection("assumption_packs")
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
        enqueued_at=data.get("enqueued_at"),
        running_at=data.get("running_at"),
        completed_at=data.get("completed_at"),
        duration_ms=data.get("duration_ms"),
        attempts=data.get("attempts", 0),
        task_name=data.get("task_name"),
        output_storage_path=data.get("output_storage_path"),
        output_download_url=data.get("output_download_url"),
        output_drive_file_id=data.get("output_drive_file_id"),
        output_folder_id=data.get("output_folder_id"),
        output_folder_url=data.get("output_folder_url"),
        output_artifacts=data.get("output_artifacts", []),
        warnings=data.get("warnings", []),
        error=data.get("error"),
        triggered_by=data.get("triggered_by", ""),
        triggered_by_email=data.get("triggered_by_email"),
        retry_of=data.get("retry_of"),
    )


def _to_summary(doc_id: str, data: dict[str, Any]) -> RunSummary:
    return RunSummary(
        id=doc_id,
        project_id=data.get("project_id", ""),
        project_name=data.get("project_name"),
        model_id=data.get("model_id", ""),
        model_name=data.get("model_name"),
        assumption_pack_id=data.get("assumption_pack_id", ""),
        assumption_pack_name=data.get("assumption_pack_name"),
        output_template_id=data.get("output_template_id", ""),
        output_template_name=data.get("output_template_name"),
        status=data.get("status", "pending"),
        started_at=data.get("started_at", datetime.now(UTC)),
        completed_at=data.get("completed_at"),
        duration_ms=data.get("duration_ms"),
        output_download_url=data.get("output_download_url"),
        triggered_by=data.get("triggered_by", ""),
        triggered_by_email=data.get("triggered_by_email"),
    )


@router.post("/api/runs", response_model=RunResponse, status_code=http_status.HTTP_202_ACCEPTED)
async def create_run(body: RunCreate, request: Request, current_user: CurrentUser):
    """Sprint C: persist Run as `pending` + enqueue (or in-thread). Returns 202.

    Frontend polls GET /api/runs/{id} until status terminal. The actual heavy
    computation runs in either:
      - Cloud Tasks worker (settings.runs_queue set) — production path
      - Background thread (settings.runs_queue empty) — local / no queue yet

    Either way the worker function is `_run_worker.execute_run_by_id`.
    """
    model, pack, tpl = _validate_or_404(
        body.model_id, body.project_id, body.assumption_pack_id, body.output_template_id
    )

    errors = run_validator.validate_run_composition(model, pack, tpl)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    user_token = request.headers.get("X-MFM-Drive-Token")
    started_at = datetime.now(UTC)
    proj_doc_for_name = _project_doc(body.project_id) or {}

    # Sprint F: encrypt the persisted Drive token via KMS so it doesn't sit
    # in Firestore in plaintext. Falls back to plaintext if KMS isn't
    # available (local dev / first deploy before setup_kms_drive_tokens.sh ran).
    drive_token_encrypted: str | None = None
    drive_token_plain: str | None = None
    if user_token:
        if secrets_svc.is_kms_available():
            try:
                drive_token_encrypted = secrets_svc.encrypt(user_token)
            except Exception as exc:  # noqa: BLE001 — fall back, don't fail the run
                import logging
                logging.getLogger(__name__).warning(
                    "KMS encrypt failed (%s); persisting Drive token in plaintext", exc
                )
                drive_token_plain = user_token
        else:
            drive_token_plain = user_token

    run_ref = _runs_ref().document()
    run_data: dict[str, Any] = {
        "project_id": body.project_id,
        "project_name": proj_doc_for_name.get("name"),
        "assumption_pack_id": body.assumption_pack_id,
        "assumption_pack_name": pack.get("name"),
        "assumption_pack_version": pack.get("version", 1),
        "assumption_pack_drive_revision_id": None,
        "model_id": body.model_id,
        "model_name": model.get("name"),
        "model_version": model.get("version", 1),
        "model_drive_revision_id": None,
        "output_template_id": body.output_template_id,
        "output_template_name": tpl.get("name"),
        "output_template_version": tpl.get("version", 1),
        "output_template_drive_revision_id": None,
        "status": "pending",
        "started_at": started_at,
        "enqueued_at": started_at,
        "attempts": 0,
        "triggered_by": current_user["uid"],
        "triggered_by_email": current_user.get("email", ""),
        # Persist Drive token so worker (running in another process) can read
        # Drive-backed packs/templates. Cleared on terminal status.
        # Sprint F: prefer drive_token_encrypted (KMS); drive_token plaintext
        # is fallback for back-compat + KMS unavailable cases.
        "drive_token_encrypted": drive_token_encrypted,
        "drive_token": drive_token_plain,
        # ⚠ Token TTL is ~1h; runs >55min from POST will fail to read Drive.
        "warnings": [],
    }
    run_ref.set(run_data)

    # Dispatch: Cloud Tasks if configured, in-thread otherwise.
    task_name = run_queue.enqueue_run(run_ref.id, drive_token=user_token)
    if task_name is None:
        # Sync mode: launch background thread so the HTTP request still returns 202.
        run_queue.execute_in_thread(run_ref.id, drive_token=user_token)
    else:
        run_ref.update({"task_name": task_name})

    return _to_response(run_ref.id, run_data)


# ── Cloud Tasks worker endpoint ──────────────────────────────────────────────


@router.post(
    "/internal/tasks/run/{run_id}",
    status_code=http_status.HTTP_200_OK,
    dependencies=[Depends(verify_cloud_tasks_request)],
)
async def run_worker(run_id: str, request: Request) -> dict[str, Any]:
    """Cloud Tasks invokes this. Browsers cannot — see verify_cloud_tasks_request.

    Body (JSON): { "run_id": "...", "drive_token": "..." (optional) }
    The drive_token is also persisted on the Run doc, so we accept either source.
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    drive_token = body.get("drive_token") if isinstance(body, dict) else None
    try:
        _run_worker.execute_run_by_id(run_id, drive_token=drive_token)
        return {"run_id": run_id, "status": "completed"}
    except Exception as exc:  # noqa: BLE001 — return 500 so Cloud Tasks may retry
        raise HTTPException(status_code=500, detail=f"Worker failed: {exc}") from exc


# ── List / detail / retry ────────────────────────────────────────────────────


@router.get("/api/runs", response_model=list[RunSummary])
async def list_runs(
    current_user: CurrentUser,
    project_id: str | None = Query(default=None),
    model_id: str | None = Query(default=None, description="Sprint G2: filter by Model"),
    assumption_pack_id: str | None = Query(default=None, description="Sprint G2"),
    output_template_id: str | None = Query(default=None, description="Sprint G2"),
    triggered_by: str | None = Query(default=None, description="Filter by user uid"),
    triggered_by_email: str | None = Query(
        default=None, description="Filter by user email (denormalized on the run)"
    ),
    status: str | None = Query(default=None),
    limit: int = Query(default=50),
):
    """Sprint UX-01-14 + G2: filter Run history by project / model / pack /
    template / user / status. Sorted descending by started_at.
    """
    q = _runs_ref()
    if project_id:
        q = q.where("project_id", "==", project_id)
    if model_id:
        q = q.where("model_id", "==", model_id)
    if assumption_pack_id:
        q = q.where("assumption_pack_id", "==", assumption_pack_id)
    if output_template_id:
        q = q.where("output_template_id", "==", output_template_id)
    if triggered_by:
        q = q.where("triggered_by", "==", triggered_by)
    if triggered_by_email:
        q = q.where("triggered_by_email", "==", triggered_by_email)
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

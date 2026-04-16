"""Scenarios router — per-Excel-Project inputs-only .xlsx files + Calculate."""
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.scenario import (
    ScenarioCreate,
    ScenarioResponse,
    ScenarioRunResponse,
    ScenarioSummary,
    ScenarioUpdate,
)
from backend.app.services import excel_template_engine, storage_service

router = APIRouter(tags=["scenarios"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _proj_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}excel_projects").document(project_id)


def _tpl_ref(template_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}excel_templates").document(template_id)


def _scn_ref(project_id: str):
    return _proj_ref(project_id).collection("scenarios")


def _run_ref(project_id: str, scenario_id: str):
    return _scn_ref(project_id).document(scenario_id).collection("runs")


def _to_scenario(doc_id: str, data: dict[str, Any]) -> ScenarioResponse:
    return ScenarioResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        project_id=data.get("project_id", ""),
        status=data.get("status", "active"),
        storage_path=data.get("storage_path", ""),
        drive_file_id=data.get("drive_file_id"),
        size_bytes=data.get("size_bytes", 0),
        version=data.get("version", 1),
        last_run=data.get("last_run"),
        created_by=data.get("created_by", ""),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


def _to_summary(doc_id: str, data: dict[str, Any]) -> ScenarioSummary:
    last = data.get("last_run") or {}
    return ScenarioSummary(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        status=data.get("status", "active"),
        version=data.get("version", 1),
        last_run_at=last.get("completed_at") or last.get("started_at"),
        last_run_status=last.get("status"),
        created_at=data.get("created_at", datetime.now(UTC)),
    )


def _load_project_and_template(project_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    proj_doc = _proj_ref(project_id).get()
    if not proj_doc.exists:
        raise HTTPException(status_code=404, detail="Excel Project not found")
    proj = proj_doc.to_dict()
    tpl_doc = _tpl_ref(proj.get("template_id", "")).get()
    if not tpl_doc.exists:
        raise HTTPException(status_code=404, detail="Template for this project is missing")
    return proj, tpl_doc.to_dict()


# ── Create / list / get ───────────────────────────────────────────────────────


@router.post(
    "/api/excel-projects/{project_id}/scenarios",
    response_model=ScenarioResponse,
    status_code=201,
)
async def create_scenario(project_id: str, body: ScenarioCreate, current_user: CurrentUser):
    """Create a Scenario. Seeds the inputs-only file from Template (or clones another scenario)."""
    proj, tpl = _load_project_and_template(project_id)

    if body.clone_from_id:
        src_doc = _scn_ref(project_id).document(body.clone_from_id).get()
        if not src_doc.exists:
            raise HTTPException(status_code=404, detail="Source scenario not found")
        src = src_doc.to_dict()
        seed_bytes = storage_service.download_xlsx(src.get("storage_path", ""))
    else:
        tpl_bytes = storage_service.download_xlsx(tpl.get("storage_path", ""))
        seed_bytes = excel_template_engine.extract_scenario_from_template(tpl_bytes)

    doc_ref = _scn_ref(project_id).document()
    safe_proj_code = storage_service.safe_name(proj.get("code_name") or proj.get("name", ""), fallback="project")
    safe_scn_code = storage_service.safe_name(body.code_name or body.name, fallback=doc_ref.id)
    storage_path = f"excel_projects/{safe_proj_code}/{safe_scn_code}/inputs_v1.xlsx"
    storage_service.upload_xlsx(
        storage_path,
        seed_bytes,
        download_filename=f"{safe_proj_code}_{safe_scn_code}_inputs.xlsx",
    )

    now = datetime.now(UTC)
    data = {
        "name": body.name,
        "code_name": safe_scn_code,
        "description": body.description,
        "project_id": project_id,
        "status": "active",
        "storage_path": storage_path,
        "drive_file_id": None,
        "size_bytes": len(seed_bytes),
        "version": 1,
        "last_run": None,
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref.set(data)
    return _to_scenario(doc_ref.id, data)


@router.get(
    "/api/excel-projects/{project_id}/scenarios",
    response_model=list[ScenarioSummary],
)
async def list_scenarios(project_id: str, current_user: CurrentUser):
    """List scenarios for an Excel Project."""
    return [_to_summary(doc.id, doc.to_dict()) for doc in _scn_ref(project_id).stream()]


@router.get(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
)
async def get_scenario(project_id: str, scenario_id: str, current_user: CurrentUser):
    """Get a single Scenario."""
    doc = _scn_ref(project_id).document(scenario_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _to_scenario(doc.id, doc.to_dict())


@router.put(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
)
async def update_scenario(
    project_id: str,
    scenario_id: str,
    body: ScenarioUpdate,
    current_user: CurrentUser,
):
    """Update scenario metadata. Does not change the file."""
    doc_ref = _scn_ref(project_id).document(scenario_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
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
    return _to_scenario(scenario_id, {**doc.to_dict(), **updates})


# ── File download / replace / archive ────────────────────────────────────────


@router.get("/api/excel-projects/{project_id}/scenarios/{scenario_id}/download")
async def download_scenario(project_id: str, scenario_id: str, current_user: CurrentUser):
    """Return a public HTTPS URL for the scenario inputs file."""
    doc = _scn_ref(project_id).document(scenario_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"download_url": storage_service.public_url(doc.to_dict().get("storage_path", ""))}


@router.post(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}/upload",
    response_model=ScenarioResponse,
)
async def upload_scenario_file(
    project_id: str,
    scenario_id: str,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
):
    """Replace the scenario's inputs .xlsx with a user-uploaded version.

    Validates that the file contains only I_ tabs before accepting.
    """
    doc_ref = _scn_ref(project_id).document(scenario_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scn = doc.to_dict()

    new_content = await file.read()
    if not new_content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(new_content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (50MB max)")

    try:
        classes = excel_template_engine.classify_bytes(new_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read .xlsx: {exc}") from exc

    if classes["output_tabs"] or classes["calc_tabs"]:
        raise HTTPException(
            status_code=400,
            detail="Scenario files must contain only I_ tabs. Unexpected tabs: "
            + ", ".join(classes["output_tabs"] + classes["calc_tabs"]),
        )
    if not classes["input_tabs"]:
        raise HTTPException(status_code=400, detail="Uploaded file has no I_ tabs.")

    new_version = scn.get("version", 1) + 1
    proj_doc = _proj_ref(project_id).get()
    proj = proj_doc.to_dict() if proj_doc.exists else {}
    safe_proj_code = storage_service.safe_name(proj.get("code_name") or proj.get("name", ""), fallback=project_id)
    safe_scn_code = scn.get("code_name", "scenario")
    storage_path = f"excel_projects/{safe_proj_code}/{safe_scn_code}/inputs_v{new_version}.xlsx"
    storage_service.upload_xlsx(
        storage_path,
        new_content,
        download_filename=file.filename or f"{safe_proj_code}_{safe_scn_code}_inputs.xlsx",
    )

    updates = {
        "storage_path": storage_path,
        "size_bytes": len(new_content),
        "version": new_version,
        "updated_at": datetime.now(UTC),
    }
    doc_ref.update(updates)
    return _to_scenario(scenario_id, {**scn, **updates})


@router.post(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}/archive",
    response_model=ScenarioResponse,
)
async def archive_scenario(project_id: str, scenario_id: str, current_user: CurrentUser):
    """Archive a scenario (non-destructive)."""
    doc_ref = _scn_ref(project_id).document(scenario_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    updates = {"status": "archived", "updated_at": datetime.now(UTC)}
    doc_ref.update(updates)
    return _to_scenario(scenario_id, {**doc.to_dict(), **updates})


# ── Calculate ─────────────────────────────────────────────────────────────────


@router.post(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}/calculate",
    response_model=ScenarioRunResponse,
)
async def calculate_scenario(
    project_id: str,
    scenario_id: str,
    request: Request,
    current_user: CurrentUser,
):
    """Overlay Scenario's I_ tabs onto Template, LibreOffice recalc, upload full workbook."""
    proj, tpl = _load_project_and_template(project_id)
    scn_ref = _scn_ref(project_id).document(scenario_id)
    scn_doc = scn_ref.get()
    if not scn_doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scn = scn_doc.to_dict()

    run_ref = _run_ref(project_id, scenario_id).document()
    started_at = datetime.now(UTC)
    t_start = time.monotonic()
    run_data: dict[str, Any] = {
        "scenario_id": scenario_id,
        "project_id": project_id,
        "status": "running",
        "started_at": started_at,
        "template_version_used": tpl.get("version", 1),
        "scenario_version_used": scn.get("version", 1),
        "started_by": current_user["uid"],
    }
    run_ref.set(run_data)

    try:
        template_bytes = storage_service.download_xlsx(tpl.get("storage_path", ""))
        scenario_bytes = storage_service.download_xlsx(scn.get("storage_path", ""))
        result = excel_template_engine.calculate(template_bytes, scenario_bytes)
        output_bytes: bytes = result["output_bytes"]

        safe_proj_code = storage_service.safe_name(proj.get("code_name") or proj.get("name", ""), fallback=project_id)
        safe_scn_code = scn.get("code_name", "scenario")
        ts = started_at.strftime("%Y%m%d_%H%M%S")
        out_filename = f"{ts}_{safe_proj_code}_{safe_scn_code}.xlsx"
        out_path = f"excel_projects/{safe_proj_code}/{safe_scn_code}/outputs/{out_filename}"
        download_url = storage_service.upload_xlsx(out_path, output_bytes, download_filename=out_filename)

        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t_start) * 1000)
        updates = {
            "status": "done",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output_storage_path": out_path,
            "output_download_url": download_url,
            "recalculated": result["recalculated"],
            "warnings": result.get("warnings", []),
        }
        run_ref.update(updates)

        scn_ref.update({
            "last_run": {
                "run_id": run_ref.id,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "done",
                "output_storage_path": out_path,
                "output_download_url": download_url,
                "duration_ms": duration_ms,
            },
            "updated_at": completed_at,
        })

        return ScenarioRunResponse(
            id=run_ref.id,
            scenario_id=scenario_id,
            project_id=project_id,
            status="done",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            template_version_used=tpl.get("version", 1),
            scenario_version_used=scn.get("version", 1),
            output_storage_path=out_path,
            output_download_url=download_url,
            warnings=result.get("warnings", []),
        )

    except Exception as exc:
        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t_start) * 1000)
        err_msg = str(exc)
        run_ref.update({
            "status": "error",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": err_msg,
        })
        scn_ref.update({
            "last_run": {
                "run_id": run_ref.id,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "error",
                "error": err_msg,
                "duration_ms": duration_ms,
            },
            "updated_at": completed_at,
        })
        raise HTTPException(status_code=500, detail=f"Calculation failed: {err_msg}") from exc


@router.get(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}/runs",
    response_model=list[ScenarioRunResponse],
)
async def list_runs(project_id: str, scenario_id: str, current_user: CurrentUser):
    """List run history for a scenario (most recent first)."""
    runs: list[ScenarioRunResponse] = []
    for doc in _run_ref(project_id, scenario_id).order_by(
        "started_at", direction="DESCENDING"
    ).stream():
        d = doc.to_dict()
        runs.append(ScenarioRunResponse(
            id=doc.id,
            scenario_id=scenario_id,
            project_id=project_id,
            status=d.get("status", "unknown"),
            started_at=d.get("started_at", datetime.now(UTC)),
            completed_at=d.get("completed_at"),
            duration_ms=d.get("duration_ms"),
            template_version_used=d.get("template_version_used", 1),
            scenario_version_used=d.get("scenario_version_used", 1),
            output_storage_path=d.get("output_storage_path"),
            output_download_url=d.get("output_download_url"),
            warnings=d.get("warnings", []),
            error=d.get("error"),
        ))
    return runs

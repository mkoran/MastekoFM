"""Scenarios router — per-Excel-Project inputs-only .xlsx files + Calculate.

Supports two backends via `storage_kind`:
  - "gcs"         — file lives in the masteko-fm-outputs bucket
  - "drive_xlsx"  — file lives as .xlsx in a user's Drive folder; "Edit in Sheets"
                    opens it in Sheets (Office mode) with no conversion.

All bytes are normalized to .xlsx at Calculate time, so the engine is identical
regardless of backend. See services/scenario_store.py for the adapter.
"""
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
from backend.app.services import (
    drive_service,
    excel_template_engine,
    scenario_store,
    storage_service,
)

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


def _settings_doc() -> dict[str, Any]:
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}settings").document("app").get()
    return doc.to_dict() or {} if doc.exists else {}


def _default_storage_kind() -> str:
    return _settings_doc().get("default_scenario_storage_kind") or scenario_store.STORAGE_KIND_GCS


def _drive_root_folder_id() -> str:
    return _settings_doc().get("drive_root_folder_id", "") or settings.drive_root_folder_id


def _to_scenario(doc_id: str, data: dict[str, Any]) -> ScenarioResponse:
    store = scenario_store.store_for_scenario(data)
    return ScenarioResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        description=data.get("description", ""),
        project_id=data.get("project_id", ""),
        status=data.get("status", "active"),
        storage_kind=data.get("storage_kind") or store.kind,
        storage_path=data.get("storage_path"),
        drive_file_id=data.get("drive_file_id"),
        edit_url=store.open_url(data),
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


def _resolve_drive_folders(
    proj_id: str, proj: dict[str, Any], project_code: str, user_token: str | None
) -> dict[str, str]:
    """Ensure the project's Drive folders exist; cache their ids on the project doc."""
    if proj.get("drive_folders"):
        return proj["drive_folders"]
    root = _drive_root_folder_id()
    if not root:
        raise HTTPException(
            status_code=400,
            detail="No Drive root folder configured. Set one in Settings before using Drive storage.",
        )
    if not user_token:
        raise HTTPException(
            status_code=400,
            detail="Drive storage requires a Google Sign-In access token. Sign in with Google, not DEV login.",
        )
    folders = drive_service.ensure_project_folders(root, project_code, user_access_token=user_token)
    _proj_ref(proj_id).update({"drive_folders": folders, "updated_at": datetime.now(UTC)})
    return folders


# ── Create / list / get ───────────────────────────────────────────────────────


@router.post(
    "/api/excel-projects/{project_id}/scenarios",
    response_model=ScenarioResponse,
    status_code=201,
)
async def create_scenario(
    project_id: str, body: ScenarioCreate, request: Request, current_user: CurrentUser
):
    """Create a Scenario. Seeds the inputs-only file from the Template (or clones another scenario).

    Respects `body.storage_kind` if provided; otherwise falls back to the workspace
    default (`/api/settings` → `default_scenario_storage_kind`). Drive storage
    requires a Google OAuth token in the X-Google-Access-Token header.
    """
    proj, tpl = _load_project_and_template(project_id)
    user_token = request.headers.get("X-Google-Access-Token")

    # Decide storage kind
    kind = body.storage_kind or _default_storage_kind()
    if kind not in (scenario_store.STORAGE_KIND_GCS, scenario_store.STORAGE_KIND_DRIVE_XLSX):
        raise HTTPException(status_code=400, detail=f"Unknown storage_kind: {kind}")

    # Produce seed bytes — from clone or from Template extract
    if body.clone_from_id:
        src_doc = _scn_ref(project_id).document(body.clone_from_id).get()
        if not src_doc.exists:
            raise HTTPException(status_code=404, detail="Source scenario not found")
        src = src_doc.to_dict()
        src_store = scenario_store.store_for_scenario(src)
        seed_bytes = src_store.read_bytes(src, user_access_token=user_token)
    else:
        tpl_bytes = storage_service.download_xlsx(tpl.get("storage_path", ""))
        seed_bytes = excel_template_engine.extract_scenario_from_template(tpl_bytes)

    doc_ref = _scn_ref(project_id).document()
    project_code = storage_service.safe_name(proj.get("code_name") or proj.get("name", ""), fallback="project")
    scenario_code = storage_service.safe_name(body.code_name or body.name, fallback=doc_ref.id)

    # Store the bytes in the chosen backend
    store = scenario_store.get_store(kind)
    existing_ctx: dict[str, Any] = {}
    if kind == scenario_store.STORAGE_KIND_DRIVE_XLSX:
        folders = _resolve_drive_folders(project_id, proj, project_code, user_token)
        existing_ctx["drive_folder_id"] = folders["inputs"]
    filename = f"{project_code}_{scenario_code}.xlsx"
    storage_fields = store.write_bytes(
        project_code=project_code,
        scenario_code=scenario_code,
        kind_label="inputs",
        version=1,
        filename=filename,
        content=seed_bytes,
        existing=existing_ctx,
        user_access_token=user_token,
    )

    now = datetime.now(UTC)
    data: dict[str, Any] = {
        "name": body.name,
        "code_name": scenario_code,
        "description": body.description,
        "project_id": project_id,
        "status": "active",
        "version": 1,
        "last_run": None,
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
        **storage_fields,
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
    """Return the scenario's edit URL — GCS public URL or Drive docs.google URL."""
    doc = _scn_ref(project_id).document(scenario_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    data = doc.to_dict()
    store = scenario_store.store_for_scenario(data)
    return {
        "download_url": store.open_url(data),
        "storage_kind": data.get("storage_kind") or store.kind,
    }


@router.post(
    "/api/excel-projects/{project_id}/scenarios/{scenario_id}/upload",
    response_model=ScenarioResponse,
)
async def upload_scenario_file(
    project_id: str,
    scenario_id: str,
    current_user: CurrentUser,
    request: Request,
    file: Annotated[UploadFile, File()],
):
    """Replace the scenario's inputs .xlsx with a user-uploaded version.

    For Drive-backed scenarios this replaces the file content in place
    (preserves the Sheets edit URL). For GCS it writes a new versioned blob.
    In both cases the scenario `version` is bumped.
    """
    doc_ref = _scn_ref(project_id).document(scenario_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scn = doc.to_dict()
    user_token = request.headers.get("X-Google-Access-Token")

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
    project_code = storage_service.safe_name(proj.get("code_name") or proj.get("name", ""), fallback=project_id)
    scenario_code = scn.get("code_name", "scenario")
    filename = file.filename or f"{project_code}_{scenario_code}.xlsx"

    store = scenario_store.store_for_scenario(scn)
    existing_ctx: dict[str, Any] = {}
    if store.kind == scenario_store.STORAGE_KIND_DRIVE_XLSX:
        folders = _resolve_drive_folders(project_id, proj, project_code, user_token)
        existing_ctx = {
            "drive_folder_id": folders["inputs"],
            "drive_file_id": scn.get("drive_file_id"),
        }
    storage_fields = store.write_bytes(
        project_code=project_code,
        scenario_code=scenario_code,
        kind_label="inputs",
        version=new_version,
        filename=filename,
        content=new_content,
        existing=existing_ctx,
        user_access_token=user_token,
    )

    updates = {**storage_fields, "version": new_version, "updated_at": datetime.now(UTC)}
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
    """Overlay Scenario's I_ tabs onto Template, LibreOffice recalc, upload full workbook.

    Output is uploaded to GCS for a stable public download link. (Optional future:
    also upload to Drive when the scenario is Drive-backed.)
    """
    proj, tpl = _load_project_and_template(project_id)
    scn_ref = _scn_ref(project_id).document(scenario_id)
    scn_doc = scn_ref.get()
    if not scn_doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scn = scn_doc.to_dict()
    user_token = request.headers.get("X-Google-Access-Token")

    run_ref = _run_ref(project_id, scenario_id).document()
    started_at = datetime.now(UTC)
    t_start = time.monotonic()

    store = scenario_store.store_for_scenario(scn)
    run_data: dict[str, Any] = {
        "scenario_id": scenario_id,
        "project_id": project_id,
        "status": "running",
        "started_at": started_at,
        "template_version_used": tpl.get("version", 1),
        "scenario_version_used": scn.get("version", 1),
        "input_storage_kind": store.kind,
        "input_storage_path": scn.get("storage_path"),
        "input_drive_file_id": scn.get("drive_file_id"),
        "input_download_url": store.open_url(scn),
        "started_by": current_user["uid"],
    }
    run_ref.set(run_data)

    try:
        template_bytes = storage_service.download_xlsx(tpl.get("storage_path", ""))
        scenario_bytes = store.read_bytes(scn, user_access_token=user_token)
        result = excel_template_engine.calculate(template_bytes, scenario_bytes)
        output_bytes: bytes = result["output_bytes"]

        project_code = storage_service.safe_name(proj.get("code_name") or proj.get("name", ""), fallback=project_id)
        scenario_code = scn.get("code_name", "scenario")
        ts = started_at.strftime("%Y%m%d_%H%M%S")
        out_filename = f"{ts}_{project_code}_{scenario_code}.xlsx"
        out_path = f"excel_projects/{project_code}/{scenario_code}/outputs/{out_filename}"
        download_url = storage_service.upload_xlsx(out_path, output_bytes, download_filename=out_filename)

        # If this is a Drive-backed scenario, also drop the output in Drive/Outputs/
        output_drive_id: str | None = None
        if store.kind == scenario_store.STORAGE_KIND_DRIVE_XLSX and user_token:
            try:
                folders = _resolve_drive_folders(project_id, proj, project_code, user_token)
                output_drive_id = drive_service.upload_file(
                    folders["outputs"], out_filename, output_bytes,
                    scenario_store.XLSX_MIME, user_access_token=user_token,
                )
            except Exception:
                # GCS copy is authoritative for the download URL; Drive is best-effort.
                pass

        completed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - t_start) * 1000)
        updates = {
            "status": "done",
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output_storage_path": out_path,
            "output_download_url": download_url,
            "output_drive_file_id": output_drive_id,
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
                "output_drive_file_id": output_drive_id,
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
            input_storage_kind=store.kind,
            input_storage_path=scn.get("storage_path"),
            input_drive_file_id=scn.get("drive_file_id"),
            input_download_url=store.open_url(scn),
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
            input_storage_kind=d.get("input_storage_kind"),
            input_storage_path=d.get("input_storage_path"),
            input_drive_file_id=d.get("input_drive_file_id"),
            input_download_url=d.get("input_download_url"),
            output_storage_path=d.get("output_storage_path"),
            output_download_url=d.get("output_download_url"),
            warnings=d.get("warnings", []),
            error=d.get("error"),
        ))
    return runs

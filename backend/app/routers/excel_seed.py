"""One-shot seed endpoint for the Excel Template MVP.

Provides POST /api/excel-seed/campus-adele that, when hit once, creates:
  - an Excel Template (uploaded by the caller as a file)
  - an Excel Project "Campus Adele"
  - two Scenarios: "Base" (from template) and "Optimistic" (cloned from Base)

Designed so Marc can log into DEV and click Calculate immediately. If the
objects already exist (matched by code_name), the endpoint is a no-op that
returns the existing ids.

The `storage_kind` form field (default: "gcs") selects where the Scenario
inputs files are stored. Use "drive_xlsx" with a Google Sign-In token to
seed Drive-backed scenarios that open in Sheets via "Edit in Sheets".
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.services import (
    drive_service,
    excel_template_engine,
    scenario_store,
    storage_service,
)

router = APIRouter(tags=["excel-seed"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

TEMPLATE_CODE = "campus_adele"
PROJECT_CODE = "campus_adele"


def _prefix() -> str:
    return settings.firestore_collection_prefix


def _find_template_by_code(code: str) -> tuple[str | None, dict[str, Any] | None]:
    db = get_firestore_client()
    for doc in db.collection(f"{_prefix()}excel_templates").stream():
        data = doc.to_dict()
        if data.get("code_name") == code:
            return doc.id, data
    return None, None


def _find_project_by_code(code: str) -> tuple[str | None, dict[str, Any] | None]:
    db = get_firestore_client()
    for doc in db.collection(f"{_prefix()}excel_projects").stream():
        data = doc.to_dict()
        if data.get("code_name") == code:
            return doc.id, data
    return None, None


def _find_scenario_by_code(project_id: str, code: str) -> tuple[str | None, dict[str, Any] | None]:
    db = get_firestore_client()
    ref = db.collection(f"{_prefix()}excel_projects").document(project_id).collection("scenarios")
    for doc in ref.stream():
        data = doc.to_dict()
        if data.get("code_name") == code:
            return doc.id, data
    return None, None


@router.post("/api/excel-seed/campus-adele")
async def seed_campus_adele(
    current_user: CurrentUser,
    request: Request,
    file: Annotated[UploadFile, File()],
    storage_kind: Annotated[str, Form()] = "gcs",
):
    """Seed the Campus Adele Template, Project and two Scenarios.

    POST with the Campus_Adele_Model*.xlsx file attached. Idempotent:
    re-running returns the existing ids rather than duplicating objects.

    storage_kind: "gcs" (default) | "drive_xlsx"
      drive_xlsx requires a Google Sign-In access token (X-MFM-Drive-Token
      header) and a drive_root_folder_id in Settings.
    """
    if storage_kind not in ("gcs", "drive_xlsx"):
        raise HTTPException(status_code=400, detail="storage_kind must be 'gcs' or 'drive_xlsx'")
    user_token = request.headers.get("X-MFM-Drive-Token")
    db = get_firestore_client()
    now = datetime.now(UTC)
    result: dict[str, Any] = {"created": [], "existing": [], "storage_kind": storage_kind}

    # 1. Template
    tpl_id, tpl_data = _find_template_by_code(TEMPLATE_CODE)
    if tpl_id:
        result["existing"].append(f"template={tpl_id}")
    else:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Upload the Campus Adele .xlsx")
        try:
            classes = excel_template_engine.classify_bytes(content)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unreadable .xlsx: {exc}") from exc
        if not classes["input_tabs"]:
            raise HTTPException(status_code=400, detail="Upload has no I_ tabs")

        tpl_ref = db.collection(f"{_prefix()}excel_templates").document()
        storage_path = f"excel_templates/{tpl_ref.id}/v1_campus_adele.xlsx"
        storage_service.upload_xlsx(storage_path, content, download_filename="campus_adele.xlsx")
        tpl_data = {
            "name": "Campus Adele (Construction-to-Perm)",
            "code_name": TEMPLATE_CODE,
            "description": "15-tab construction-to-permanent financing model. 5 I_ input tabs, 1 O_ output tab.",
            "version": 1,
            "input_tabs": classes["input_tabs"],
            "output_tabs": classes["output_tabs"],
            "calc_tabs": classes["calc_tabs"],
            "storage_path": storage_path,
            "drive_file_id": None,
            "size_bytes": len(content),
            "uploaded_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        }
        tpl_ref.set(tpl_data)
        tpl_id = tpl_ref.id
        result["created"].append(f"template={tpl_id}")

    # 2. Project
    proj_id, proj_data = _find_project_by_code(PROJECT_CODE)
    if proj_id:
        result["existing"].append(f"project={proj_id}")
    else:
        proj_ref = db.collection(f"{_prefix()}excel_projects").document()
        proj_data = {
            "name": "Campus Adele",
            "code_name": PROJECT_CODE,
            "description": "Seeded by /api/excel-seed/campus-adele",
            "template_id": tpl_id,
            "template_name": tpl_data.get("name", ""),
            "template_version_pinned": tpl_data.get("version", 1),
            "status": "active",
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        }
        proj_ref.set(proj_data)
        proj_id = proj_ref.id
        result["created"].append(f"project={proj_id}")

    # Shared helper: place a scenario's seed bytes in the chosen backend.
    store = scenario_store.get_store(storage_kind)
    drive_inputs_folder_id: str | None = None
    if storage_kind == scenario_store.STORAGE_KIND_DRIVE_XLSX:
        if not user_token:
            raise HTTPException(
                status_code=400,
                detail="storage_kind=drive_xlsx requires Google Sign-In (send X-MFM-Drive-Token header).",
            )
        # Resolve the drive root folder from settings (fall back to env).
        settings_doc = db.collection(f"{_prefix()}settings").document("app").get()
        root = (settings_doc.to_dict() or {}).get("drive_root_folder_id") if settings_doc.exists else None
        root = root or settings.drive_root_folder_id
        if not root:
            raise HTTPException(status_code=400, detail="No Drive root folder configured; set it in Settings first.")
        folders = drive_service.ensure_project_folders(root, PROJECT_CODE, user_access_token=user_token)
        drive_inputs_folder_id = folders["inputs"]
        # Also persist onto the project doc for the scenarios router.
        db.collection(f"{_prefix()}excel_projects").document(proj_id).update({
            "drive_folders": folders, "updated_at": now,
        })

    def _place_scenario(code_name: str, content: bytes) -> dict[str, Any]:
        existing_ctx: dict[str, Any] = {}
        if storage_kind == scenario_store.STORAGE_KIND_DRIVE_XLSX:
            existing_ctx["drive_folder_id"] = drive_inputs_folder_id
        return store.write_bytes(
            project_code=PROJECT_CODE,
            scenario_code=code_name,
            kind_label="inputs",
            version=1,
            filename=f"{PROJECT_CODE}_{code_name}.xlsx",
            content=content,
            existing=existing_ctx,
            user_access_token=user_token,
        )

    # 3. Scenario: Base
    base_id, base_data = _find_scenario_by_code(proj_id, "base")
    if base_id:
        result["existing"].append(f"scenario:base={base_id}")
    else:
        tpl_bytes = storage_service.download_xlsx(tpl_data.get("storage_path", ""))
        seed_bytes = excel_template_engine.extract_scenario_from_template(tpl_bytes)
        scn_ref = db.collection(f"{_prefix()}excel_projects").document(proj_id).collection("scenarios").document()
        storage_fields = _place_scenario("base", seed_bytes)
        base_data = {
            "name": "Base",
            "code_name": "base",
            "description": "Initial scenario seeded from Campus Adele template (literal values from the original file).",
            "project_id": proj_id,
            "status": "active",
            "version": 1,
            "last_run": None,
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
            **storage_fields,
        }
        scn_ref.set(base_data)
        base_id = scn_ref.id
        result["created"].append(f"scenario:base={base_id}")

    # 4. Scenario: Optimistic (cloned from Base via the same store)
    opt_id, opt_data = _find_scenario_by_code(proj_id, "optimistic")
    if opt_id:
        result["existing"].append(f"scenario:optimistic={opt_id}")
    else:
        # Read Base bytes through whichever store holds it.
        base_store = scenario_store.store_for_scenario(base_data)
        base_bytes = base_store.read_bytes(base_data, user_access_token=user_token)
        scn_ref = db.collection(f"{_prefix()}excel_projects").document(proj_id).collection("scenarios").document()
        storage_fields = _place_scenario("optimistic", base_bytes)
        opt_data = {
            "name": "Optimistic",
            "code_name": "optimistic",
            "description": "Cloned from Base. Edit and re-upload (or open in Sheets for Drive-backed scenarios) to try what-ifs.",
            "project_id": proj_id,
            "status": "active",
            "version": 1,
            "last_run": None,
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
            **storage_fields,
        }
        scn_ref.set(opt_data)
        opt_id = scn_ref.id
        result["created"].append(f"scenario:optimistic={opt_id}")

    return {
        "template_id": tpl_id,
        "project_id": proj_id,
        "scenario_base_id": base_id,
        "scenario_optimistic_id": opt_id,
        **result,
    }

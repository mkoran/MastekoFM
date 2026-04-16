"""One-shot seed endpoint for the Excel Template MVP.

Provides POST /api/excel-seed/campus-adele that, when hit once, creates:
  - an Excel Template (uploaded by the caller as a file)
  - an Excel Project "Campus Adele"
  - two Scenarios: "Base" (from template) and "Optimistic" (cloned from Base)

Designed so Marc can log into DEV and click Calculate immediately. If the
objects already exist (matched by code_name), the endpoint is a no-op that
returns the existing ids.
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.services import excel_template_engine, storage_service

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
    file: Annotated[UploadFile, File()],
):
    """Seed the Campus Adele Template, Project and two Scenarios.

    POST with the Campus_Adele_Model*.xlsx file attached. Idempotent:
    re-running returns the existing ids rather than duplicating objects.
    """
    db = get_firestore_client()
    now = datetime.now(UTC)
    result: dict[str, Any] = {"created": [], "existing": []}

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

    # 3. Scenario: Base
    base_id, base_data = _find_scenario_by_code(proj_id, "base")
    if base_id:
        result["existing"].append(f"scenario:base={base_id}")
    else:
        tpl_bytes = storage_service.download_xlsx(tpl_data.get("storage_path", ""))
        seed_bytes = excel_template_engine.extract_scenario_from_template(tpl_bytes)
        scn_ref = db.collection(f"{_prefix()}excel_projects").document(proj_id).collection("scenarios").document()
        storage_path = f"excel_projects/{PROJECT_CODE}/base/inputs_v1.xlsx"
        storage_service.upload_xlsx(storage_path, seed_bytes, download_filename=f"{PROJECT_CODE}_base_inputs.xlsx")
        base_data = {
            "name": "Base",
            "code_name": "base",
            "description": "Initial scenario seeded from Campus Adele template (literal values from the original file).",
            "project_id": proj_id,
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
        scn_ref.set(base_data)
        base_id = scn_ref.id
        result["created"].append(f"scenario:base={base_id}")

    # 4. Scenario: Optimistic (cloned from Base)
    opt_id, opt_data = _find_scenario_by_code(proj_id, "optimistic")
    if opt_id:
        result["existing"].append(f"scenario:optimistic={opt_id}")
    else:
        base_bytes = storage_service.download_xlsx(base_data.get("storage_path", ""))
        scn_ref = db.collection(f"{_prefix()}excel_projects").document(proj_id).collection("scenarios").document()
        storage_path = f"excel_projects/{PROJECT_CODE}/optimistic/inputs_v1.xlsx"
        storage_service.upload_xlsx(storage_path, base_bytes, download_filename=f"{PROJECT_CODE}_optimistic_inputs.xlsx")
        opt_data = {
            "name": "Optimistic",
            "code_name": "optimistic",
            "description": "Cloned from Base — edit the .xlsx directly in GCS or upload a new version to try what-ifs.",
            "project_id": proj_id,
            "status": "active",
            "storage_path": storage_path,
            "drive_file_id": None,
            "size_bytes": len(base_bytes),
            "version": 1,
            "last_run": None,
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
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

"""Seed endpoints — populate DEV with canonical scenarios from seed/* files.

Idempotent: re-running returns existing IDs rather than creating duplicates.
Matched by code_name.

Sprint A: only /api/seed/helloworld. Sprint B rewrites /api/seed/campus-adele.
"""
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.services import drive_service, excel_template_engine, storage_service

router = APIRouter(tags=["seed"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/app/routers/seed.py -> repo root
SEED_DIR = REPO_ROOT / "seed" / "helloworld"

HW_MODEL_NAME = "Hello World Model"
HW_MODEL_CODE = "helloworld_model"
HW_PACK_NAME = "Hello World Inputs"
HW_PACK_CODE = "helloworld_inputs"
HW_TEMPLATE_NAME = "Hello World Report"
HW_TEMPLATE_CODE = "helloworld_report"
HW_PROJECT_NAME = "Hello World"
HW_PROJECT_CODE = "helloworld"


def _prefix() -> str:
    return settings.firestore_collection_prefix


def _drive_root_id() -> str:
    doc = get_firestore_client().collection(f"{_prefix()}settings").document("app").get()
    if doc.exists:
        return (doc.to_dict() or {}).get("drive_root_folder_id") or settings.drive_root_folder_id
    return settings.drive_root_folder_id


def _find_by_code(collection: str, code: str) -> tuple[str | None, dict[str, Any] | None]:
    db = get_firestore_client()
    for doc in db.collection(collection).stream():
        data = doc.to_dict()
        if data.get("code_name") == code:
            return doc.id, data
    return None, None


def _find_pack_by_code(project_id: str, code: str) -> tuple[str | None, dict[str, Any] | None]:
    db = get_firestore_client()
    ref = db.collection(f"{_prefix()}excel_projects").document(project_id).collection("scenarios")
    for doc in ref.stream():
        data = doc.to_dict()
        if data.get("code_name") == code:
            return doc.id, data
    return None, None


@router.post("/api/seed/helloworld")
async def seed_helloworld(current_user: CurrentUser, request: Request):
    """Idempotent: uploads 3 Hello World seed files and creates a Project.

    Requires Google Sign-In (X-MFM-Drive-Token header) since OutputTemplates and the
    AssumptionPack are Drive-backed.
    """
    user_token = request.headers.get("X-MFM-Drive-Token")
    if not user_token:
        raise HTTPException(
            status_code=400,
            detail="Hello World seed requires Google Sign-In (X-MFM-Drive-Token header).",
        )

    root = _drive_root_id()
    if not root:
        raise HTTPException(
            status_code=400, detail="No Drive root folder configured. Set one in Settings first."
        )

    # Verify seed files exist
    model_path = SEED_DIR / "helloworld_model.xlsx"
    pack_path = SEED_DIR / "helloworld_inputs.xlsx"
    tpl_path = SEED_DIR / "helloworld_report.xlsx"
    for p in (model_path, pack_path, tpl_path):
        if not p.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Seed file missing: {p}. Run scripts/build_helloworld_seed.py first.",
            )

    db = get_firestore_client()
    now = datetime.now(UTC)
    result: dict[str, Any] = {"created": [], "existing": []}

    # ── 1. Hello World Model ────────────────────────────────────────────────
    # Models still live in `excel_templates` collection (Sprint A — rename in B)
    model_id, model_data = _find_by_code(f"{_prefix()}excel_templates", HW_MODEL_CODE)
    if model_id:
        result["existing"].append(f"model={model_id}")
    else:
        content = model_path.read_bytes()
        classes = excel_template_engine.classify_bytes(content)
        # Models go to GCS in Sprint A (Sprint B may move them to Drive)
        model_ref = db.collection(f"{_prefix()}excel_templates").document()
        storage_path = f"excel_templates/{model_ref.id}/v1_helloworld_model.xlsx"
        storage_service.upload_xlsx(storage_path, content, download_filename="helloworld_model.xlsx")
        model_data = {
            "name": HW_MODEL_NAME,
            "code_name": HW_MODEL_CODE,
            "description": "Tiny Hello World Model: I_Numbers (a, b) → O_Results (sum, product).",
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
        model_ref.set(model_data)
        model_id = model_ref.id
        result["created"].append(f"model={model_id}")

    # ── 2. Hello World OutputTemplate ───────────────────────────────────────
    tpl_id, tpl_data = _find_by_code(f"{_prefix()}output_templates", HW_TEMPLATE_CODE)
    if tpl_id:
        result["existing"].append(f"output_template={tpl_id}")
    else:
        content = tpl_path.read_bytes()
        classes = excel_template_engine.classify_bytes(content)
        # OutputTemplates go to Drive
        mfm = drive_service.find_or_create_folder("MastekoFM", root, user_token)
        tpl_folder = drive_service.find_or_create_folder("OutputTemplates", mfm, user_token)
        drive_id = drive_service.upload_file(
            tpl_folder, "helloworld_report.xlsx", content, XLSX_MIME, user_access_token=user_token
        )
        tpl_ref = db.collection(f"{_prefix()}output_templates").document()
        tpl_data = {
            "name": HW_TEMPLATE_NAME,
            "code_name": HW_TEMPLATE_CODE,
            "description": "Hello World Report: pulls Model O_Results into M_Results, displays in O_Report.",
            "format": "xlsx",
            "version": 1,
            "storage_kind": "drive_xlsx",
            "storage_path": None,
            "drive_file_id": drive_id,
            "m_tabs": classes["m_tabs"],
            "output_tabs": classes["output_tabs"],
            "calc_tabs": classes["calc_tabs"],
            "size_bytes": len(content),
            "uploaded_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        }
        tpl_ref.set(tpl_data)
        tpl_id = tpl_ref.id
        result["created"].append(f"output_template={tpl_id}")

    # ── 3. Hello World Project ──────────────────────────────────────────────
    proj_id, proj_data = _find_by_code(f"{_prefix()}excel_projects", HW_PROJECT_CODE)
    if proj_id:
        result["existing"].append(f"project={proj_id}")
    else:
        proj_ref = db.collection(f"{_prefix()}excel_projects").document()
        # Provision Drive folders for the project
        folders = drive_service.ensure_project_folders(
            root, HW_PROJECT_CODE, user_access_token=user_token
        )
        proj_data = {
            "name": HW_PROJECT_NAME,
            "code_name": HW_PROJECT_CODE,
            "description": "Tiny Hello World Project — verifies three-way composition end-to-end.",
            "template_id": model_id,  # legacy field name pre-Sprint-B
            "template_name": HW_MODEL_NAME,
            "template_version_pinned": 1,
            "status": "active",
            "drive_folders": folders,
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        }
        proj_ref.set(proj_data)
        proj_id = proj_ref.id
        result["created"].append(f"project={proj_id}")

    # ── 4. Hello World AssumptionPack (Drive-backed) ─────────────────────────
    pack_id, pack_data = _find_pack_by_code(proj_id, HW_PACK_CODE)
    if pack_id:
        result["existing"].append(f"assumption_pack={pack_id}")
    else:
        content = pack_path.read_bytes()
        classes = excel_template_engine.classify_bytes(content)
        # Packs go to Drive under <root>/MastekoFM/<project>/Inputs/
        folders = (proj_data or {}).get("drive_folders") or drive_service.ensure_project_folders(
            root, HW_PROJECT_CODE, user_access_token=user_token
        )
        drive_id = drive_service.upload_file(
            folders["inputs"],
            "helloworld_inputs.xlsx",
            content,
            XLSX_MIME,
            user_access_token=user_token,
        )
        pack_ref = (
            db.collection(f"{_prefix()}excel_projects")
            .document(proj_id)
            .collection("scenarios")
            .document()
        )
        pack_data = {
            "name": HW_PACK_NAME,
            "code_name": HW_PACK_CODE,
            "description": "Hello World inputs: a=5, b=7. Expected outputs: sum=12, product=35, total=47.",
            "project_id": proj_id,
            "status": "active",
            "storage_kind": "drive_xlsx",
            "storage_path": None,
            "drive_file_id": drive_id,
            "size_bytes": len(content),
            "version": 1,
            "input_tabs": classes["input_tabs"],
            "last_run": None,
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        }
        pack_ref.set(pack_data)
        pack_id = pack_ref.id
        result["created"].append(f"assumption_pack={pack_id}")

    return {
        "model_id": model_id,
        "output_template_id": tpl_id,
        "project_id": proj_id,
        "assumption_pack_id": pack_id,
        **result,
    }

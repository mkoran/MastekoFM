"""Seed endpoints — populate DEV with canonical scenarios from seed/* files.

Sprint B: rewritten under the new entity/collection names:
  - models      (was excel_templates)
  - projects    (was excel_projects)
  - assumption_packs  (was scenarios, as a per-project subcollection)

Both /api/seed/helloworld and /api/seed/campus-adele are idempotent: re-running
returns the existing IDs rather than duplicating objects.
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

REPO_ROOT = Path(__file__).resolve().parents[3]


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
    ref = db.collection(f"{_prefix()}projects").document(project_id).collection("assumption_packs")
    for doc in ref.stream():
        data = doc.to_dict()
        if data.get("code_name") == code:
            return doc.id, data
    return None, None


def _seed_one(
    *,
    seed_dir: Path,
    model_filename: str,
    pack_filename: str,
    output_template_filename: str,
    model_name: str,
    model_code: str,
    model_description: str,
    pack_name: str,
    pack_code: str,
    pack_description: str,
    template_name: str,
    template_code: str,
    template_description: str,
    project_name: str,
    project_code: str,
    project_description: str,
    user_token: str,
    current_user: dict,
) -> dict[str, Any]:
    """Generic seeder used by both Hello World and Campus Adele endpoints."""
    root = _drive_root_id()
    if not root:
        raise HTTPException(status_code=400, detail="No Drive root folder configured.")

    db = get_firestore_client()
    now = datetime.now(UTC)
    result: dict[str, Any] = {"created": [], "existing": []}

    model_path = seed_dir / model_filename
    pack_path = seed_dir / pack_filename
    tpl_path = seed_dir / output_template_filename
    for p in (model_path, pack_path, tpl_path):
        if not p.exists():
            raise HTTPException(status_code=500, detail=f"Seed file missing: {p}")

    # ── 1. Model ────────────────────────────────────────────────────────────
    model_id, model_data = _find_by_code(f"{_prefix()}models", model_code)
    if model_id:
        result["existing"].append(f"model={model_id}")
    else:
        content = model_path.read_bytes()
        classes = excel_template_engine.classify_bytes(content)
        model_ref = db.collection(f"{_prefix()}models").document()
        storage_path = f"models/{model_ref.id}/v1_{model_filename}"
        storage_service.upload_xlsx(storage_path, content, download_filename=model_filename)
        model_data = {
            "name": model_name,
            "code_name": model_code,
            "description": model_description,
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

    # ── 2. OutputTemplate (Drive-backed) ────────────────────────────────────
    tpl_id, tpl_data = _find_by_code(f"{_prefix()}output_templates", template_code)
    if tpl_id:
        result["existing"].append(f"output_template={tpl_id}")
    else:
        content = tpl_path.read_bytes()
        classes = excel_template_engine.classify_bytes(content)
        mfm = drive_service.find_or_create_folder("MastekoFM", root, user_token)
        tpl_folder = drive_service.find_or_create_folder("OutputTemplates", mfm, user_token)
        drive_id = drive_service.upload_file(
            tpl_folder, output_template_filename, content, XLSX_MIME, user_access_token=user_token
        )
        tpl_ref = db.collection(f"{_prefix()}output_templates").document()
        tpl_data = {
            "name": template_name,
            "code_name": template_code,
            "description": template_description,
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

    # ── 3. Project ──────────────────────────────────────────────────────────
    proj_id, proj_data = _find_by_code(f"{_prefix()}projects", project_code)
    if proj_id:
        result["existing"].append(f"project={proj_id}")
    else:
        proj_ref = db.collection(f"{_prefix()}projects").document()
        folders = drive_service.ensure_project_folders(
            root, project_code, user_access_token=user_token
        )
        proj_data = {
            "name": project_name,
            "code_name": project_code,
            "description": project_description,
            "default_model_id": model_id,
            "default_model_name": model_name,
            "default_model_version": 1,
            "status": "active",
            "drive_folders": folders,
            "created_by": current_user["uid"],
            "created_at": now,
            "updated_at": now,
        }
        proj_ref.set(proj_data)
        proj_id = proj_ref.id
        result["created"].append(f"project={proj_id}")

    # ── 4. AssumptionPack (Drive-backed) ────────────────────────────────────
    pack_id, pack_data = _find_pack_by_code(proj_id, pack_code)
    if pack_id:
        result["existing"].append(f"assumption_pack={pack_id}")
    else:
        content = pack_path.read_bytes()
        classes = excel_template_engine.classify_bytes(content)
        folders = (proj_data or {}).get("drive_folders") or drive_service.ensure_project_folders(
            root, project_code, user_access_token=user_token
        )
        drive_id = drive_service.upload_file(
            folders["inputs"], pack_filename, content, XLSX_MIME, user_access_token=user_token,
        )
        pack_ref = (
            db.collection(f"{_prefix()}projects")
            .document(proj_id)
            .collection("assumption_packs")
            .document()
        )
        pack_data = {
            "name": pack_name,
            "code_name": pack_code,
            "description": pack_description,
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


# ── HELLO WORLD ──────────────────────────────────────────────────────────────


@router.post("/api/seed/helloworld")
async def seed_helloworld(current_user: CurrentUser, request: Request):
    """Idempotent: uploads 3 Hello World seed files + creates a Project."""
    user_token = request.headers.get("X-MFM-Drive-Token")
    if not user_token:
        raise HTTPException(
            status_code=400, detail="Hello World seed requires X-MFM-Drive-Token header.",
        )
    return _seed_one(
        seed_dir=REPO_ROOT / "seed" / "helloworld",
        model_filename="helloworld_model.xlsx",
        pack_filename="helloworld_inputs.xlsx",
        output_template_filename="helloworld_report.xlsx",
        model_name="Hello World Model",
        model_code="helloworld_model",
        model_description="Tiny Hello World Model: I_Numbers (a, b) → O_Results (sum, product).",
        pack_name="Hello World Inputs",
        pack_code="helloworld_inputs",
        pack_description="Hello World inputs: a=5, b=7. Expected outputs: sum=12, product=35, total=47.",
        template_name="Hello World Report",
        template_code="helloworld_report",
        template_description="Hello World Report: pulls Model O_Results into M_Results, displays in O_Report.",
        project_name="Hello World",
        project_code="helloworld",
        project_description="Tiny Hello World Project — verifies three-way composition end-to-end.",
        user_token=user_token,
        current_user=current_user,
    )


# ── CAMPUS ADELE ─────────────────────────────────────────────────────────────


@router.post("/api/seed/campus-adele")
async def seed_campus_adele(current_user: CurrentUser, request: Request):
    """Idempotent: uploads Campus Adele Model + Base AssumptionPack + Investor Summary OutputTemplate."""
    user_token = request.headers.get("X-MFM-Drive-Token")
    if not user_token:
        raise HTTPException(
            status_code=400, detail="Campus Adele seed requires X-MFM-Drive-Token header.",
        )
    return _seed_one(
        seed_dir=REPO_ROOT / "seed" / "campus_adele",
        model_filename="campus_adele_model.xlsx",
        pack_filename="campus_adele_base_pack.xlsx",
        output_template_filename="campus_adele_summary.xlsx",
        model_name="Campus Adele (Construction-to-Perm)",
        model_code="campus_adele_model",
        model_description="15-tab construction-to-permanent financing model. 5 I_ input tabs, 1 O_ output tab.",
        pack_name="Base Case",
        pack_code="campus_adele_base",
        pack_description="Base Case AssumptionPack — 64 units, 170 budget items, all I_ tabs populated.",
        template_name="Investor Summary v1",
        template_code="campus_adele_summary",
        template_description="Minimal investor summary — surfaces Annual Summary cells from the Model.",
        project_name="Campus Adele",
        project_code="campus_adele",
        project_description="Real construction-to-perm financing project — Quebec, 64 units.",
        user_token=user_token,
        current_user=current_user,
    )

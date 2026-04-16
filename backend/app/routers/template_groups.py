"""Template Groups + Template Group Values router."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.template_group import (
    TemplateGroupCreate,
    TemplateGroupResponse,
    TemplateGroupUpdate,
    TGVCreate,
    TGVResponse,
    TGVSummary,
    TGVUpdate,
)

router = APIRouter(tags=["template-groups"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _tg_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}template_groups")


def _tgv_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id).collection("tgv")


def _to_tg(doc_id: str, data: dict[str, Any]) -> TemplateGroupResponse:
    return TemplateGroupResponse(
        id=doc_id,
        name=data.get("name", ""),
        description=data.get("description", ""),
        code_name=data.get("code_name", ""),
        template_ids=data.get("template_ids", []),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


def _to_tgv(doc_id: str, data: dict[str, Any]) -> TGVResponse:
    return TGVResponse(
        id=doc_id,
        name=data.get("name", ""),
        code_name=data.get("code_name", ""),
        project_id=data.get("project_id", ""),
        template_group_id=data.get("template_group_id", ""),
        version=data.get("version", 1),
        values=data.get("values", {}),
        table_data=data.get("table_data", {}),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


# ─── Template Group CRUD ───

@router.post("/api/template-groups", response_model=TemplateGroupResponse, status_code=201)
async def create_template_group(body: TemplateGroupCreate, current_user: CurrentUser):
    """Create a new template group."""
    now = datetime.now(UTC)
    data = {
        "name": body.name,
        "description": body.description,
        "code_name": body.code_name or body.name.replace(" ", "_")[:20],
        "template_ids": body.template_ids,
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = _tg_ref().document()
    doc_ref.set(data)
    return _to_tg(doc_ref.id, data)


@router.get("/api/template-groups", response_model=list[TemplateGroupResponse])
async def list_template_groups(current_user: CurrentUser):
    """List all template groups."""
    docs = _tg_ref().stream()
    return [_to_tg(doc.id, doc.to_dict()) for doc in docs]


@router.get("/api/template-groups/{group_id}", response_model=TemplateGroupResponse)
async def get_template_group(group_id: str, current_user: CurrentUser):
    """Get a single template group."""
    doc = _tg_ref().document(group_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Template group not found")
    return _to_tg(doc.id, doc.to_dict())


@router.put("/api/template-groups/{group_id}", response_model=TemplateGroupResponse)
async def update_template_group(group_id: str, body: TemplateGroupUpdate, current_user: CurrentUser):
    """Update a template group."""
    doc_ref = _tg_ref().document(group_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Template group not found")

    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.code_name is not None:
        updates["code_name"] = body.code_name
    if body.template_ids is not None:
        updates["template_ids"] = body.template_ids

    doc_ref.update(updates)
    return _to_tg(group_id, {**doc.to_dict(), **updates})


@router.delete("/api/template-groups/{group_id}", status_code=204)
async def delete_template_group(group_id: str, current_user: CurrentUser):
    """Delete a template group."""
    doc_ref = _tg_ref().document(group_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Template group not found")
    doc_ref.delete()


# ─── Template Group Values (Scenarios) — per project ───

@router.post("/api/projects/{project_id}/scenarios", response_model=TGVResponse, status_code=201)
async def create_scenario(project_id: str, body: TGVCreate, current_user: CurrentUser):
    """Create a new scenario (Template Group Value) for a project."""
    prefix = settings.firestore_collection_prefix
    db = get_firestore_client()

    # Get project to find its template group
    project_doc = db.collection(f"{prefix}projects").document(project_id).get()
    if not project_doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    project_data = project_doc.to_dict()
    tg_id = project_data.get("template_group_id", "")

    now = datetime.now(UTC)
    values: dict[str, Any] = {}
    table_data: dict[str, list[dict[str, Any]]] = {}

    # Clone from existing TGV if requested
    if body.clone_from_id:
        src_doc = _tgv_ref(project_id).document(body.clone_from_id).get()
        if src_doc.exists:
            src = src_doc.to_dict()
            values = src.get("values", {})
            table_data = src.get("table_data", {})

    data = {
        "name": body.name,
        "code_name": body.code_name or body.name.replace(" ", "_")[:20],
        "project_id": project_id,
        "template_group_id": tg_id,
        "version": 1,
        "values": values,
        "table_data": table_data,
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = _tgv_ref(project_id).document()
    doc_ref.set(data)
    return _to_tgv(doc_ref.id, data)


@router.get("/api/projects/{project_id}/scenarios", response_model=list[TGVSummary])
async def list_scenarios(project_id: str, current_user: CurrentUser):
    """List all scenarios for a project (without full values for performance)."""
    docs = _tgv_ref(project_id).stream()
    return [
        TGVSummary(
            id=doc.id,
            name=doc.to_dict().get("name", ""),
            code_name=doc.to_dict().get("code_name", ""),
            version=doc.to_dict().get("version", 1),
            created_at=doc.to_dict().get("created_at", datetime.now(UTC)),
            updated_at=doc.to_dict().get("updated_at", datetime.now(UTC)),
        )
        for doc in docs
    ]


@router.get("/api/projects/{project_id}/scenarios/{scenario_id}", response_model=TGVResponse)
async def get_scenario(project_id: str, scenario_id: str, current_user: CurrentUser):
    """Get a single scenario with all values."""
    doc = _tgv_ref(project_id).document(scenario_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _to_tgv(doc.id, doc.to_dict())


@router.put("/api/projects/{project_id}/scenarios/{scenario_id}", response_model=TGVResponse)
async def update_scenario(
    project_id: str, scenario_id: str, body: TGVUpdate, current_user: CurrentUser
):
    """Update a scenario. Bumps version on value changes."""
    doc_ref = _tgv_ref(project_id).document(scenario_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")

    data = doc.to_dict()
    now = datetime.now(UTC)
    updates: dict[str, Any] = {"updated_at": now}

    if body.name is not None:
        updates["name"] = body.name
    if body.code_name is not None:
        updates["code_name"] = body.code_name
    if body.values is not None:
        updates["values"] = body.values
        updates["version"] = data.get("version", 1) + 1
    if body.table_data is not None:
        updates["table_data"] = body.table_data
        updates["version"] = data.get("version", 1) + 1

    doc_ref.update(updates)
    return _to_tgv(scenario_id, {**data, **updates})


@router.delete("/api/projects/{project_id}/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(project_id: str, scenario_id: str, current_user: CurrentUser):
    """Delete a scenario."""
    doc_ref = _tgv_ref(project_id).document(scenario_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Scenario not found")
    doc_ref.delete()


# ─── Apply Template Group to Project ───

@router.post("/api/projects/{project_id}/apply-group/{group_id}", status_code=201)
async def apply_template_group(project_id: str, group_id: str, current_user: CurrentUser):
    """Apply a template group to a project.

    Sets the project's template_group_id and creates a default "Base Case" scenario
    with all key-values and tables from the templates in the group.
    """
    prefix = settings.firestore_collection_prefix
    db = get_firestore_client()

    # Verify group exists
    tg_doc = _tg_ref().document(group_id).get()
    if not tg_doc.exists:
        raise HTTPException(status_code=404, detail="Template group not found")
    tg = tg_doc.to_dict()

    # Set template group on project
    project_ref = db.collection(f"{prefix}projects").document(project_id)
    project_ref.update({
        "template_group_id": group_id,
        "template_group_name": tg.get("name", ""),
        "updated_at": datetime.now(UTC),
    })

    # Collect all assumptions from all templates in the group
    values: dict[str, Any] = {}
    table_data: dict[str, list[dict[str, Any]]] = {}

    templates_ref = db.collection(f"{prefix}assumption_templates")
    for tmpl_id in tg.get("template_ids", []):
        tmpl_doc = templates_ref.document(tmpl_id).get()
        if not tmpl_doc.exists:
            continue
        tmpl = tmpl_doc.to_dict()

        # Key-values
        for kv in tmpl.get("key_values", []):
            values[kv["key"]] = kv.get("default_value")

        # Tables (store column definitions + empty rows)
        for tbl in tmpl.get("tables", []):
            table_data[tbl["key"]] = []  # Empty rows, user fills in

    # Create "Base Case" TGV
    now = datetime.now(UTC)
    tgv_data = {
        "name": "Base Case",
        "code_name": "base_case",
        "project_id": project_id,
        "template_group_id": group_id,
        "version": 1,
        "values": values,
        "table_data": table_data,
        "created_by": current_user["uid"],
        "created_at": now,
        "updated_at": now,
    }
    tgv_ref = _tgv_ref(project_id).document()
    tgv_ref.set(tgv_data)

    return {
        "message": f"Template group applied. Base Case created with {len(values)} values and {len(table_data)} tables.",
        "template_group_id": group_id,
        "base_case_id": tgv_ref.id,
        "values_count": len(values),
        "tables_count": len(table_data),
    }


# ─── App Settings ───

@router.get("/api/settings")
async def get_settings(current_user: CurrentUser):
    """Get app-level settings."""
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}settings").document("app").get()
    if not doc.exists:
        return {
            "drive_root_folder_id": settings.drive_root_folder_id,
            "default_scenario_storage_kind": "gcs",
        }
    data = doc.to_dict()
    return {
        "drive_root_folder_id": data.get("drive_root_folder_id", settings.drive_root_folder_id),
        "default_scenario_storage_kind": data.get("default_scenario_storage_kind", "gcs"),
    }


@router.put("/api/settings")
async def update_settings(body: dict[str, Any], current_user: CurrentUser):
    """Update app-level settings."""
    prefix = settings.firestore_collection_prefix
    doc_ref = get_firestore_client().collection(f"{prefix}settings").document("app")
    updates = {"updated_at": datetime.now(UTC), "updated_by": current_user["uid"]}
    if "drive_root_folder_id" in body:
        updates["drive_root_folder_id"] = body["drive_root_folder_id"]
    if "default_scenario_storage_kind" in body:
        kind = body["default_scenario_storage_kind"]
        if kind not in ("gcs", "drive_xlsx"):
            raise HTTPException(status_code=400, detail="default_scenario_storage_kind must be 'gcs' or 'drive_xlsx'")
        updates["default_scenario_storage_kind"] = kind
    doc_ref.set(updates, merge=True)
    return {"message": "Settings updated"}


@router.post("/api/settings/test-storage")
async def test_storage_connection(current_user: CurrentUser):
    """Test that Cloud Storage is accessible for output files."""
    try:
        from google.cloud import storage as gcs

        client = gcs.Client(project=settings.gcp_project)
        bucket = client.bucket("masteko-fm-outputs")

        # Write test
        blob = bucket.blob("_connection_test.txt")
        blob.upload_from_string(b"MastekoFM storage test", content_type="text/plain")

        # Delete test
        blob.delete()

        return {
            "success": True,
            "message": "Cloud Storage OK. Bucket 'masteko-fm-outputs' is writable. Output files will be available for download after calculation.",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/settings/test-drive")
async def test_drive_connection(request: Request, current_user: CurrentUser):
    """Test Drive folder access using the user's Google token."""
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}settings").document("app").get()
    folder_id = doc.to_dict().get("drive_root_folder_id") if doc.exists else settings.drive_root_folder_id

    if not folder_id:
        return {"success": False, "error": "No Drive folder configured. Save a folder ID first."}

    google_token = request.headers.get("X-MFM-Drive-Token")
    if not google_token:
        return {"success": False, "error": "No Google access token. Sign in with Google (not DEV login) to test Drive access."}

    try:
        from backend.app.services.drive_service import _get_drive_service

        service = _get_drive_service(user_access_token=google_token)

        # Read test
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            pageSize=5,
            supportsAllDrives=True,
        ).execute()
        file_count = len(results.get("files", []))

        # Write test
        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(b"MastekoFM Drive test", mimetype="text/plain")
        test_file = service.files().create(
            body={"name": "_masteko_test.txt", "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()

        # Delete test
        service.files().delete(fileId=test_file["id"], supportsAllDrives=True).execute()

        return {
            "success": True,
            "message": f"Drive connection OK! Folder has {file_count} files. Read + write + delete all working.",
            "folder_id": folder_id,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "folder_id": folder_id}

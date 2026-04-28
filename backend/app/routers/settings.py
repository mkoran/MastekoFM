"""Workspace-level settings — Drive root folder, default scenario storage, etc.

Lives in `{prefix}settings/app` Firestore doc. Single doc per environment.
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user

router = APIRouter(tags=["settings"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _settings_doc():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}settings").document("app")


@router.get("/api/settings")
async def get_settings(current_user: CurrentUser):
    doc = _settings_doc().get()
    if not doc.exists:
        return {
            "drive_root_folder_id": settings.drive_root_folder_id,
            "default_scenario_storage_kind": "drive_xlsx",
        }
    data = doc.to_dict()
    return {
        "drive_root_folder_id": data.get("drive_root_folder_id", settings.drive_root_folder_id),
        "default_scenario_storage_kind": data.get("default_scenario_storage_kind", "drive_xlsx"),
    }


@router.put("/api/settings")
async def update_settings(body: dict[str, Any], current_user: CurrentUser):
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC), "updated_by": current_user["uid"]}
    if "drive_root_folder_id" in body:
        updates["drive_root_folder_id"] = body["drive_root_folder_id"]
    if "default_scenario_storage_kind" in body:
        kind = body["default_scenario_storage_kind"]
        if kind not in ("gcs", "drive_xlsx"):
            raise HTTPException(
                status_code=400,
                detail="default_scenario_storage_kind must be 'gcs' or 'drive_xlsx'",
            )
        updates["default_scenario_storage_kind"] = kind
    _settings_doc().set(updates, merge=True)
    return {"message": "Settings updated"}


@router.post("/api/settings/test-storage")
async def test_storage_connection(current_user: CurrentUser):
    """Verify GCS bucket is writable for output blobs."""
    try:
        from google.cloud import storage as gcs

        client = gcs.Client(project=settings.gcp_project)
        bucket = client.bucket("masteko-fm-outputs")
        blob = bucket.blob("_connection_test.txt")
        blob.upload_from_string(b"MastekoFM storage test", content_type="text/plain")
        blob.delete()
        return {
            "success": True,
            "message": "Cloud Storage OK. Bucket 'masteko-fm-outputs' is writable.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/settings/test-drive")
async def test_drive_connection(request: Request, current_user: CurrentUser):
    """Verify the user's Google OAuth token can read+write+delete in their Drive folder."""
    doc = _settings_doc().get()
    folder_id = (
        doc.to_dict().get("drive_root_folder_id") if doc.exists else settings.drive_root_folder_id
    )
    if not folder_id:
        return {
            "success": False,
            "error": "No Drive folder configured. Save a folder ID first.",
        }

    google_token = request.headers.get("X-MFM-Drive-Token")
    if not google_token:
        return {
            "success": False,
            "error": "No Google access token. Sign in with Google (not DEV login) to test Drive access.",
        }

    try:
        from googleapiclient.http import MediaInMemoryUpload

        from backend.app.services.drive_service import _get_drive_service

        service = _get_drive_service(user_access_token=google_token)
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            pageSize=5,
            supportsAllDrives=True,
        ).execute()
        file_count = len(results.get("files", []))

        media = MediaInMemoryUpload(b"MastekoFM Drive test", mimetype="text/plain")
        test_file = service.files().create(
            body={"name": "_masteko_test.txt", "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        service.files().delete(fileId=test_file["id"], supportsAllDrives=True).execute()
        return {
            "success": True,
            "message": f"Drive connection OK! Folder has {file_count} files. Read + write + delete all working.",
            "folder_id": folder_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "folder_id": folder_id}

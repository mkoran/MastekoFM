"""Google Drive service — folder and file operations."""
import io
import logging

from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _get_drive_service():
    """Get authenticated Drive API service."""
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_project_folder(project_name: str) -> str | None:
    """Create a project folder in Google Drive under MastekoFM root."""
    root_folder_id = settings.drive_root_folder_id
    if not root_folder_id:
        logger.warning("DRIVE_ROOT_FOLDER_ID not set — skipping folder creation")
        return None

    service = _get_drive_service()
    try:
        project_folder = service.files().create(
            body={
                "name": project_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [root_folder_id],
            },
            fields="id",
        ).execute()
        project_folder_id = project_folder["id"]

        for subfolder_name in ["sources", "spreadsheets", "reports"]:
            service.files().create(
                body={
                    "name": subfolder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [project_folder_id],
                },
                fields="id",
            ).execute()

        logger.info("Created Drive folder for project '%s': %s", project_name, project_folder_id)
        return project_folder_id

    except Exception:
        logger.exception("Failed to create Drive folder for project '%s'", project_name)
        raise


def upload_file(folder_id: str, filename: str, content: bytes, mime_type: str) -> str | None:
    """Upload a file to a Google Drive folder. Returns file ID."""
    try:
        service = _get_drive_service()
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        result = service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id",
        ).execute()
        return result["id"]
    except Exception:
        logger.exception("Failed to upload file '%s'", filename)
        return None


def download_file(file_id: str) -> bytes | None:
    """Download a file from Google Drive. Returns file content."""
    try:
        service = _get_drive_service()
        content = service.files().get_media(fileId=file_id).execute()
        return content
    except Exception:
        logger.exception("Failed to download file '%s'", file_id)
        return None


def list_files(folder_id: str) -> list[dict]:
    """List files in a Google Drive folder."""
    try:
        service = _get_drive_service()
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name, mimeType, modifiedTime, size)",
            orderBy="modifiedTime desc",
        ).execute()
        return results.get("files", [])
    except Exception:
        logger.exception("Failed to list files in folder '%s'", folder_id)
        return []

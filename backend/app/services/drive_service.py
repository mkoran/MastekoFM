"""Google Drive service — folder and file operations."""
import io
import logging

from google.auth import default
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from backend.app.config import settings

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"


def _get_drive_service(user_access_token: str | None = None):
    """Get authenticated Drive API service.

    If user_access_token is provided, uses the user's Google OAuth token
    (needed for personal Gmail Drive access). Otherwise uses the SA.
    """
    if user_access_token:
        creds = Credentials(token=user_access_token)
    else:
        creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_project_folder(project_name: str, user_access_token: str | None = None) -> str | None:
    """Create a project folder in Google Drive under MastekoFM root."""
    root_folder_id = settings.drive_root_folder_id
    if not root_folder_id:
        logger.warning("DRIVE_ROOT_FOLDER_ID not set — skipping folder creation")
        return None

    service = _get_drive_service(user_access_token)
    try:
        project_folder = service.files().create(
            body={
                "name": project_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [root_folder_id],
            },
            fields="id",
            supportsAllDrives=True,
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
                supportsAllDrives=True,
            ).execute()

        logger.info("Created Drive folder for project '%s': %s", project_name, project_folder_id)
        return project_folder_id

    except Exception:
        logger.exception("Failed to create Drive folder for project '%s'", project_name)
        raise


def upload_file(folder_id: str, filename: str, content: bytes, mime_type: str, user_access_token: str | None = None) -> str | None:
    """Upload a file to a Google Drive folder. Returns file ID.

    Uses supportsAllDrives=True for Shared Drive compatibility.
    """
    try:
        service = _get_drive_service(user_access_token)
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        result = service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        logger.info("Uploaded '%s' to Drive folder %s: %s", filename, folder_id, result["id"])
        return result["id"]
    except Exception as e:
        logger.exception("Failed to upload file '%s' to folder '%s'", filename, folder_id)
        # Don't swallow — let caller handle
        raise RuntimeError(f"Drive upload failed: {e}") from e


def download_file(file_id: str, user_access_token: str | None = None) -> bytes | None:
    """Download a file's raw bytes from Google Drive.

    When the file is a native Google-apps type (Doc, Sheet, Slide) this call
    fails — callers who need that should use `export_file()` instead.
    Here we always want .xlsx bytes, which are returned verbatim.
    """
    try:
        service = _get_drive_service(user_access_token)
        content = service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
        return content
    except Exception:
        logger.exception("Failed to download file '%s'", file_id)
        return None


def update_file_content(
    file_id: str,
    content: bytes,
    mime_type: str,
    user_access_token: str | None = None,
) -> str | None:
    """Replace a Drive file's content in place. Preserves the file id and URL.

    This is what enables "Edit in Sheets" links to stay stable across
    scenario version bumps — we rewrite bytes, not the file identity.
    """
    try:
        service = _get_drive_service(user_access_token)
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        result = service.files().update(
            fileId=file_id, media_body=media, fields="id", supportsAllDrives=True,
        ).execute()
        return result.get("id")
    except Exception as e:
        logger.exception("Failed to update file '%s'", file_id)
        raise RuntimeError(f"Drive update failed: {e}") from e


def find_or_create_folder(
    name: str,
    parent_id: str,
    user_access_token: str | None = None,
) -> str:
    """Return the id of a child folder with this name under parent_id, creating if needed."""
    service = _get_drive_service(user_access_token)
    existing = service.files().list(
        q=f"'{parent_id}' in parents and mimeType='{FOLDER_MIME}' and name='{name}' and trashed=false",
        fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    if existing:
        return existing[0]["id"]
    created = service.files().create(
        body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
        fields="id", supportsAllDrives=True,
    ).execute()
    return created["id"]


def ensure_project_folders(
    root_folder_id: str,
    project_code: str,
    user_access_token: str | None = None,
) -> dict[str, str]:
    """Ensure the Drive folder layout exists for a project.

    Creates (idempotently):
      <root>/MastekoFM/<project_code>/Inputs/
      <root>/MastekoFM/<project_code>/Outputs/

    Returns {"project": id, "inputs": id, "outputs": id}.
    """
    mfm = find_or_create_folder("MastekoFM", root_folder_id, user_access_token)
    proj = find_or_create_folder(project_code, mfm, user_access_token)
    inputs = find_or_create_folder("Inputs", proj, user_access_token)
    outputs = find_or_create_folder("Outputs", proj, user_access_token)
    return {"project": proj, "inputs": inputs, "outputs": outputs}


def list_files(folder_id: str, user_access_token: str | None = None) -> list[dict]:
    """List files in a Google Drive folder."""
    try:
        service = _get_drive_service(user_access_token)
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name, mimeType, modifiedTime, size)",
            orderBy="modifiedTime desc",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        return results.get("files", [])
    except Exception:
        logger.exception("Failed to list files in folder '%s'", folder_id)
        return []

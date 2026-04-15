"""Google Drive service — folder and file operations."""
import logging

from google.auth import default
from googleapiclient.discovery import build

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _get_drive_service():
    """Get authenticated Drive API service."""
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_project_folder(project_name: str) -> str | None:
    """Create a project folder in Google Drive under MastekoFM root.

    Structure: MastekoFM/{project_name}/
                ├── sources/
                ├── spreadsheets/
                └── reports/

    Returns the folder ID, or None if Drive is not configured.
    """
    root_folder_id = settings.drive_root_folder_id
    if not root_folder_id:
        logger.warning("DRIVE_ROOT_FOLDER_ID not set — skipping folder creation")
        return None

    try:
        service = _get_drive_service()

        # Create project folder
        project_folder = service.files().create(
            body={
                "name": project_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [root_folder_id],
            },
            fields="id",
        ).execute()
        project_folder_id = project_folder["id"]

        # Create subfolders
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
        return None

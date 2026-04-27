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
    """LEGACY (Sprint B layout) — Ensure flat <root>/MastekoFM/<project>/{Inputs,Outputs}/.

    Kept for back-compat with existing data only. New code uses the workspace
    layout: see ensure_workspace_folders + ensure_pack_folder + ensure_run_folder.
    """
    mfm = find_or_create_folder("MastekoFM", root_folder_id, user_access_token)
    proj = find_or_create_folder(project_code, mfm, user_access_token)
    inputs = find_or_create_folder("Inputs", proj, user_access_token)
    outputs = find_or_create_folder("Outputs", proj, user_access_token)
    return {"project": proj, "inputs": inputs, "outputs": outputs}


# ── Sprint G1 — versioned filename + workspace folder layout ─────────────────


def versioned_filename(code: str, version: int, ext: str = "xlsx") -> str:
    """Sprint G1: canonical filename encoding.

    Every artifact lives at `{code}_v{NNN}.{ext}` where NNN is zero-padded.
    Sortable by name = sortable by version = sortable by upload time
    (since versions bump monotonically with time).

    Examples:
      versioned_filename("helloworld_inputs", 1)        → "helloworld_inputs_v001.xlsx"
      versioned_filename("campus_adele_model", 27)      → "campus_adele_model_v027.xlsx"
      versioned_filename("output", 1, ext="pdf")        → "output_v001.pdf"
    """
    if version < 1:
        raise ValueError(f"version must be >= 1, got {version}")
    return f"{code}_v{version:03d}.{ext}"


def run_folder_name(started_at_utc, pack_code: str, tpl_code: str) -> str:
    """Sprint G1: per-run folder name `{YYYYMMDD-HHMMSS}_{pack}_{tpl}`."""
    ts = started_at_utc.strftime("%Y%m%d-%H%M%S")
    return f"{ts}_{pack_code}_{tpl_code}"


def ensure_workspace_folders(
    root_folder_id: str,
    workspace_code: str,
    user_access_token: str | None = None,
) -> dict[str, str]:
    """Sprint G1: ensure the workspace layout exists.

    Creates (idempotent):
      <root>/MastekoFM/Workspaces/<ws_code>/
                                      ├── Models/
                                      ├── OutputTemplates/
                                      └── Projects/

    Returns {"workspace": id, "models": id, "output_templates": id, "projects": id}.
    """
    mfm = find_or_create_folder("MastekoFM", root_folder_id, user_access_token)
    workspaces = find_or_create_folder("Workspaces", mfm, user_access_token)
    ws = find_or_create_folder(workspace_code, workspaces, user_access_token)
    models = find_or_create_folder("Models", ws, user_access_token)
    tpls = find_or_create_folder("OutputTemplates", ws, user_access_token)
    projects = find_or_create_folder("Projects", ws, user_access_token)
    return {
        "workspace": ws,
        "models": models,
        "output_templates": tpls,
        "projects": projects,
    }


def ensure_model_folder(
    models_folder_id: str,
    model_code: str,
    user_access_token: str | None = None,
) -> str:
    """Sprint G1: per-Model folder under workspace's Models/."""
    return find_or_create_folder(model_code, models_folder_id, user_access_token)


def ensure_output_template_folder(
    output_templates_folder_id: str,
    tpl_code: str,
    user_access_token: str | None = None,
) -> str:
    """Sprint G1: per-OutputTemplate folder under workspace's OutputTemplates/."""
    return find_or_create_folder(tpl_code, output_templates_folder_id, user_access_token)


def ensure_project_folder_v2(
    projects_folder_id: str,
    project_code: str,
    user_access_token: str | None = None,
) -> dict[str, str]:
    """Sprint G1: per-Project folder under workspace's Projects/, with subfolders.

    Creates:
      <projects>/<project_code>/
                      ├── AssumptionPacks/
                      └── Runs/
    """
    proj = find_or_create_folder(project_code, projects_folder_id, user_access_token)
    packs = find_or_create_folder("AssumptionPacks", proj, user_access_token)
    runs = find_or_create_folder("Runs", proj, user_access_token)
    return {"project": proj, "packs": packs, "runs": runs}


def ensure_pack_folder(
    packs_folder_id: str,
    pack_code: str,
    user_access_token: str | None = None,
) -> str:
    """Sprint G1: per-AssumptionPack folder."""
    return find_or_create_folder(pack_code, packs_folder_id, user_access_token)


def ensure_run_folder(
    runs_folder_id: str,
    folder_name: str,
    user_access_token: str | None = None,
) -> str:
    """Sprint G1: per-Run folder under project's Runs/. Use run_folder_name() for the name."""
    return find_or_create_folder(folder_name, runs_folder_id, user_access_token)


def folder_url(folder_id: str | None) -> str | None:
    """Convenience: build a Drive folder web URL from an id."""
    if not folder_id:
        return None
    return f"https://drive.google.com/drive/folders/{folder_id}"


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

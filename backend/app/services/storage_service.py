"""Cloud Storage helper for Excel Template / Scenario / Output files.

Uses the existing masteko-fm-outputs bucket for all Excel Template MVP artifacts.
Files are organized by kind:

  excel_templates/<template_id>/v<N>_<filename>.xlsx
  excel_projects/<project_code>/<scenario_code>/inputs_v<N>.xlsx
  excel_projects/<project_code>/<scenario_code>/outputs/<timestamp>_<project>_<scenario>.xlsx

Public-read on the bucket gives plain HTTPS download URLs — matches existing
dag_executor.py convention (see that file for the pattern).
"""
import logging

from backend.app.config import settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "masteko-fm-outputs"
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _client():
    """Lazy GCS client (matches dag_executor.py pattern)."""
    from google.cloud import storage as gcs
    return gcs.Client(project=settings.gcp_project)


def upload_xlsx(blob_path: str, content: bytes, download_filename: str | None = None) -> str:
    """Upload a .xlsx to GCS and return a plain HTTPS download URL.

    blob_path: object key inside the bucket (no leading slash).
    download_filename: if provided, sets Content-Disposition so the browser
                       downloads with this name rather than the object key.
    """
    client = _client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)
    if download_filename:
        blob.content_disposition = f'attachment; filename="{download_filename}"'
    blob.upload_from_string(content, content_type=XLSX_CONTENT_TYPE)
    url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"
    logger.info("Uploaded %d bytes to %s", len(content), url)
    return url


def download_xlsx(blob_path: str) -> bytes:
    """Download a .xlsx from GCS by object path."""
    client = _client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()


def delete_blob(blob_path: str) -> bool:
    """Delete a blob. Returns True if deleted, False if missing."""
    client = _client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)
    try:
        blob.delete()
        return True
    except Exception:
        logger.exception("Failed to delete blob %s", blob_path)
        return False


def public_url(blob_path: str) -> str:
    """Build a public HTTPS URL for a blob without hitting the network."""
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"


def safe_name(raw: str, fallback: str = "item") -> str:
    """Sanitize a string for use in a blob path segment."""
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in (raw or "").strip())
    return cleaned or fallback

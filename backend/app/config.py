"""Application configuration — loads from env + Secret Manager."""
import os
from pathlib import Path

from pydantic_settings import BaseSettings


def _read_version() -> str:
    """Read VERSION file from project root."""
    version_path = Path(__file__).resolve().parents[2] / "VERSION"
    if version_path.exists():
        return version_path.read_text().strip()
    return "0.0.0"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    environment: str = os.getenv("ENVIRONMENT", "local")
    version: str = _read_version()
    gcp_project: str = "masteko-fm"
    gcp_region: str = "northamerica-northeast1"
    firestore_collection_prefix: str = os.getenv("FIRESTORE_PREFIX", "dev_")
    dev_auth_bypass: bool = os.getenv("DEV_AUTH_BYPASS", "false").lower() == "true"
    drive_root_folder_id: str = os.getenv("DRIVE_ROOT_FOLDER_ID", "")

    # Sprint C — async runs via Cloud Tasks
    runs_queue: str = os.getenv("RUNS_QUEUE", "")  # e.g. "mfm-runs-dev". Empty = sync mode.
    runs_worker_url: str = os.getenv("RUNS_WORKER_URL", "")  # base URL for /internal/tasks/run/{id}
    runs_worker_sa: str = os.getenv("RUNS_WORKER_SA", "")  # SA email Cloud Tasks uses for OIDC

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def init_firebase() -> None:
    """Initialize Firebase Admin SDK. Call lazily, not at import time."""
    import firebase_admin

    if not firebase_admin._apps:
        firebase_admin.initialize_app()


def get_firestore_client():
    """Get a Firestore client. Lazy initialization for test compatibility."""
    from google.cloud import firestore

    return firestore.Client(project=settings.gcp_project)

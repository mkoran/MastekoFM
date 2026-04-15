"""Application configuration — loads from env + Secret Manager."""
import os
from pathlib import Path

import firebase_admin
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def _init_firebase() -> None:
    """Initialize Firebase Admin SDK if not already initialized."""
    if not firebase_admin._apps:
        firebase_admin.initialize_app()


_init_firebase()

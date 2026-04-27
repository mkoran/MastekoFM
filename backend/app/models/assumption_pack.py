"""Pydantic models for Scenarios (per-Excel-Project input files)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AssumptionPackCreate(BaseModel):
    """Request body for creating a Scenario.

    Seeds the Scenario file from the Project's Template (I_ tabs only) unless
    clone_from_id is provided, in which case the Scenario file is copied from
    the existing scenario.

    storage_kind overrides the workspace default (see /api/settings) and
    determines whether the file lives in GCS or Drive.
    """

    name: str
    code_name: str = ""
    description: str = ""
    clone_from_id: str | None = None
    storage_kind: str | None = None  # "gcs" | "drive_xlsx" | None (use default)


class AssumptionPackUpdate(BaseModel):
    """Metadata update. File replacement is a separate upload endpoint."""

    name: str | None = None
    code_name: str | None = None
    description: str | None = None
    status: str | None = None


class AssumptionPackResponse(BaseModel):
    """Full AssumptionPack record."""

    id: str
    name: str
    code_name: str
    description: str
    project_id: str
    pack_number: int = 0              # Sprint G3: per-project counter 1..99 (0 = legacy/unassigned)
    status: str                       # active | archived
    archived: bool = False            # Sprint UX-01: explicit boolean
    storage_kind: str = "drive_xlsx"  # Sprint UX-01: default Drive (post-Sprint-B)
    storage_path: str | None = None   # GCS path when storage_kind=gcs
    drive_folder_id: str | None = None  # Sprint G1: per-pack folder
    drive_folder_url: str | None = None  # Sprint G1: derived URL
    drive_file_id: str | None = None  # latest version's file id
    edit_url: str | None = None       # URL to open in Sheets / download, chosen per store
    size_bytes: int
    version: int                      # increments on every inputs-file replacement
    last_run: dict[str, Any] | None = None  # {run_id, at, status, output_path, ...}
    created_by: str
    created_by_email: str | None = None  # Sprint UX-01
    created_at: datetime
    updated_at: datetime


class AssumptionPackSummary(BaseModel):
    """List-view summary."""

    id: str
    name: str
    code_name: str
    pack_number: int = 0  # Sprint G3
    status: str
    archived: bool = False  # Sprint UX-01
    version: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_by_email: str | None = None  # Sprint UX-01
    created_at: datetime


class AssumptionPackRunResponse(BaseModel):
    """A single calculation run (legacy /api/projects/{p}/assumption-packs/{s}/runs).

    Sprint A introduced the canonical Run model in models/run.py — this stays
    here only for the legacy assumption_packs router compatibility surface.
    """

    id: str
    scenario_id: str
    project_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    template_version_used: int
    scenario_version_used: int
    input_storage_kind: str | None = None
    input_storage_path: str | None = None
    input_drive_file_id: str | None = None
    input_download_url: str | None = None
    output_storage_path: str | None = None
    output_download_url: str | None = None
    warnings: list[str] = []
    error: str | None = None

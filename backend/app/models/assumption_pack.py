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
    """Full Scenario record."""

    id: str
    name: str
    code_name: str
    description: str
    project_id: str
    status: str                       # active | archived
    storage_kind: str = "gcs"         # gcs | drive_xlsx
    storage_path: str | None = None   # GCS path when storage_kind=gcs
    drive_file_id: str | None = None  # Drive file id when storage_kind=drive_xlsx
    edit_url: str | None = None       # URL to open in Sheets / download, chosen per store
    size_bytes: int
    version: int                      # increments on every inputs-file replacement
    last_run: dict[str, Any] | None = None  # {run_id, at, status, output_path, ...}
    created_by: str
    created_at: datetime
    updated_at: datetime


class AssumptionPackSummary(BaseModel):
    """List-view summary."""

    id: str
    name: str
    code_name: str
    status: str
    version: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
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

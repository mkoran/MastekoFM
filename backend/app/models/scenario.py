"""Pydantic models for Scenarios (per-Excel-Project input files)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScenarioCreate(BaseModel):
    """Request body for creating a Scenario.

    Seeds the Scenario file from the Project's Template (I_ tabs only) unless
    clone_from_id is provided, in which case the Scenario file is copied from
    the existing scenario.
    """

    name: str
    code_name: str = ""
    description: str = ""
    clone_from_id: str | None = None


class ScenarioUpdate(BaseModel):
    """Metadata update. File replacement is a separate upload endpoint."""

    name: str | None = None
    code_name: str | None = None
    description: str | None = None
    status: str | None = None


class ScenarioResponse(BaseModel):
    """Full Scenario record."""

    id: str
    name: str
    code_name: str
    description: str
    project_id: str
    status: str                       # active | archived
    storage_path: str                 # gs:// path of the inputs-only xlsx
    drive_file_id: str | None = None
    size_bytes: int
    version: int                      # increments on every inputs-file replacement
    last_run: dict[str, Any] | None = None  # {run_id, at, status, output_path, ...}
    created_by: str
    created_at: datetime
    updated_at: datetime


class ScenarioSummary(BaseModel):
    """List-view summary."""

    id: str
    name: str
    code_name: str
    status: str
    version: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_at: datetime


class ScenarioRunResponse(BaseModel):
    """A single calculation run."""

    id: str
    scenario_id: str
    project_id: str
    status: str                       # running | done | error
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    template_version_used: int
    scenario_version_used: int
    output_storage_path: str | None = None
    output_download_url: str | None = None
    warnings: list[str] = []
    error: str | None = None

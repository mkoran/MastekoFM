"""Pydantic models for Runs (top-level Firestore collection).

A Run is an immutable record of one three-way composition execution:
  (AssumptionPack vN, Model vM, OutputTemplate vO) -> output artifact

Sprint A: synchronous execution.
Sprint C: async via Cloud Tasks; status moves pending -> running -> completed/failed.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RunCreate(BaseModel):
    """Body for POST /api/runs — the three-way composition."""

    project_id: str
    assumption_pack_id: str
    model_id: str
    output_template_id: str


class RunValidateRequest(BaseModel):
    """Body for POST /api/runs/validate — preview compatibility before submit."""

    model_id: str
    assumption_pack_id: str
    output_template_id: str


class RunValidateResponse(BaseModel):
    """Result of compatibility check."""

    compatible: bool
    errors: list[str]


class RunSummary(BaseModel):
    """List-view summary for /api/runs and /api/projects/{p}/runs."""

    id: str
    project_id: str
    project_name: str | None = None
    model_id: str
    model_name: str | None = None
    assumption_pack_id: str
    assumption_pack_name: str | None = None
    output_template_id: str
    output_template_name: str | None = None
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    output_download_url: str | None = None
    triggered_by: str
    triggered_by_email: str | None = None  # Sprint UX-01: for "Created By" filter on Runs page


class RunResponse(BaseModel):
    """Full Run record."""

    id: str
    project_id: str

    # Composition (versioned + revision-pinned for reproducibility)
    assumption_pack_id: str
    assumption_pack_version: int
    assumption_pack_drive_revision_id: str | None = None
    model_id: str
    model_version: int
    model_drive_revision_id: str | None = None
    output_template_id: str
    output_template_version: int
    output_template_drive_revision_id: str | None = None

    # Execution
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    started_at: datetime
    enqueued_at: datetime | None = None  # Sprint C
    running_at: datetime | None = None  # Sprint C
    completed_at: datetime | None = None
    duration_ms: int | None = None
    attempts: int = 0  # Sprint C — retry tracking
    task_name: str | None = None  # Sprint C — Cloud Tasks resource path

    # Result
    output_storage_path: str | None = None
    output_download_url: str | None = None
    output_drive_file_id: str | None = None
    output_folder_id: str | None = None       # Sprint G1: per-run Drive folder
    output_folder_url: str | None = None      # Sprint G1: derived URL
    output_artifacts: list[dict] = []         # Sprint G1: [{format, drive_file_id, download_url, size_bytes}, ...]
    warnings: list[str] = []
    error: str | None = None

    # Audit
    triggered_by: str
    triggered_by_email: str | None = None  # Sprint UX-01
    retry_of: str | None = None  # if this is a retry, the prior run id

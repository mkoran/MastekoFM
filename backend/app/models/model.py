"""Pydantic models for Excel Templates (the new tab-prefix based template system).

An Excel Template is an uploaded .xlsx whose tab prefixes declare the contract:
  - I_*   -> input tabs (humans edit these in Scenarios)
  - O_*   -> output tabs (computed; never edited)
  - other -> calc tabs (formulas only, not touched by users)

Case-sensitive prefix match. "i_Foo" is a calc tab, NOT an input tab.
"""
from datetime import datetime

from pydantic import BaseModel


class ModelSummary(BaseModel):
    """Lightweight Excel Template for list views."""

    id: str
    name: str
    code_name: str
    workspace_id: str | None = None  # Sprint G1
    version: int
    input_tab_count: int
    output_tab_count: int
    calc_tab_count: int
    archived: bool = False  # Sprint UX-01
    drive_folder_url: str | None = None  # Sprint G1: per-Model folder URL
    drive_url: str | None = None  # Sprint UX-01: opens in Sheets/Drive
    created_by_email: str | None = None  # Sprint UX-01
    created_at: datetime
    updated_at: datetime


class ModelResponse(BaseModel):
    """Full Excel Template record."""

    id: str
    name: str
    code_name: str
    description: str
    workspace_id: str | None = None  # Sprint G1
    version: int
    input_tabs: list[str]
    output_tabs: list[str]
    calc_tabs: list[str]
    storage_path: str | None = None   # legacy GCS path; new Models are Drive-only
    drive_folder_id: str | None = None  # Sprint G1: per-Model folder
    drive_folder_url: str | None = None  # Sprint G1: derived URL of the folder
    drive_file_id: str | None = None    # the canonical (latest) .xlsx
    drive_url: str | None = None  # Sprint UX-01: derived edit URL of the .xlsx
    size_bytes: int
    archived: bool = False  # Sprint UX-01
    uploaded_by: str
    uploaded_by_email: str | None = None  # Sprint UX-01
    created_at: datetime
    updated_at: datetime


class ModelUpdate(BaseModel):
    """Metadata update (file content is replaced via re-upload)."""

    name: str | None = None
    description: str | None = None
    code_name: str | None = None
    drive_file_id: str | None = None  # Sprint UX-01-16: swap to a different Drive file
    archived: bool | None = None  # Sprint UX-01

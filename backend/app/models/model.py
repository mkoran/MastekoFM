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
    version: int
    input_tab_count: int
    output_tab_count: int
    calc_tab_count: int
    created_at: datetime
    updated_at: datetime


class ModelResponse(BaseModel):
    """Full Excel Template record."""

    id: str
    name: str
    code_name: str
    description: str
    version: int
    input_tabs: list[str]
    output_tabs: list[str]
    calc_tabs: list[str]
    storage_path: str                 # gs:// path (or drive:<file_id>)
    drive_file_id: str | None = None
    size_bytes: int
    uploaded_by: str
    created_at: datetime
    updated_at: datetime


class ModelUpdate(BaseModel):
    """Metadata update (file content is replaced via re-upload)."""

    name: str | None = None
    description: str | None = None
    code_name: str | None = None

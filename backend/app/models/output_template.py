"""Pydantic models for OutputTemplates.

An OutputTemplate is the third entity in three-way composition. For format=xlsx
it's another .xlsx with M_/calc/O_ tabs (M_ tabs filled by Model O_ outputs).
For format=pdf|docx|google_doc it's a placeholder template (Sprint D, H).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class OutputTemplateSummary(BaseModel):
    """Lightweight summary for list views."""

    id: str
    name: str
    code_name: str
    format: str
    version: int
    m_tab_count: int
    output_tab_count: int
    calc_tab_count: int
    created_at: datetime
    updated_at: datetime


class OutputTemplateResponse(BaseModel):
    """Full OutputTemplate record."""

    id: str
    name: str
    code_name: str
    description: str
    format: Literal["xlsx"] = "xlsx"  # Future: "pdf" | "docx" | "google_doc"
    version: int
    storage_kind: str = "drive_xlsx"
    storage_path: str | None = None
    drive_file_id: str | None = None
    edit_url: str | None = None
    m_tabs: list[str]
    output_tabs: list[str]
    calc_tabs: list[str]
    size_bytes: int
    uploaded_by: str
    created_at: datetime
    updated_at: datetime


class OutputTemplateUpdate(BaseModel):
    """Metadata-only update (file replacement is via re-upload)."""

    name: str | None = None
    code_name: str | None = None
    description: str | None = None

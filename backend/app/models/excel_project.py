"""Pydantic models for Excel Projects (tab-overlay based)."""
from datetime import datetime

from pydantic import BaseModel


class ExcelProjectCreate(BaseModel):
    """Request body for creating an Excel Project."""

    name: str
    code_name: str = ""
    description: str = ""
    template_id: str


class ExcelProjectUpdate(BaseModel):
    """Request body for updating an Excel Project."""

    name: str | None = None
    code_name: str | None = None
    description: str | None = None
    status: str | None = None  # "active" | "archived"


class ExcelProjectResponse(BaseModel):
    """Excel Project record."""

    id: str
    name: str
    code_name: str
    description: str
    template_id: str
    template_name: str
    template_version_pinned: int
    status: str                       # active | archived
    created_by: str
    created_at: datetime
    updated_at: datetime


class ExcelProjectSummary(BaseModel):
    """List-view summary."""

    id: str
    name: str
    code_name: str
    template_id: str
    template_name: str
    status: str
    scenario_count: int
    created_at: datetime

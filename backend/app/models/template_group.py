"""Pydantic models for Template Groups and Template Group Values."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ─── Template Group ───

class TemplateGroupCreate(BaseModel):
    """Request to create a template group."""

    name: str
    description: str = ""
    code_name: str = ""
    template_ids: list[str] = []


class TemplateGroupUpdate(BaseModel):
    """Request to update a template group."""

    name: str | None = None
    description: str | None = None
    code_name: str | None = None
    template_ids: list[str] | None = None


class TemplateGroupResponse(BaseModel):
    """Template group returned by the API."""

    id: str
    name: str
    description: str
    code_name: str
    template_ids: list[str]
    created_at: datetime
    updated_at: datetime


# ─── Template Group Values (Scenarios) ───

class TGVCreate(BaseModel):
    """Request to create a Template Group Value (scenario)."""

    name: str
    code_name: str = ""
    clone_from_id: str | None = None  # Clone values from another TGV


class TGVUpdate(BaseModel):
    """Request to update a TGV."""

    name: str | None = None
    code_name: str | None = None
    values: dict[str, Any] | None = None  # {assumption_key: value}
    table_data: dict[str, list[dict[str, Any]]] | None = None  # {table_key: [{row}, ...]}


class TGVResponse(BaseModel):
    """Template Group Value returned by the API."""

    id: str
    name: str
    code_name: str
    project_id: str
    template_group_id: str
    version: int
    values: dict[str, Any]
    table_data: dict[str, list[dict[str, Any]]]
    created_at: datetime
    updated_at: datetime


class TGVSummary(BaseModel):
    """Lightweight TGV for listing (without full values)."""

    id: str
    name: str
    code_name: str
    version: int
    created_at: datetime
    updated_at: datetime

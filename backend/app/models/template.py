"""Pydantic models for assumption templates."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from backend.app.models.assumption import AssumptionType, ColumnDef


class TemplateKeyValue(BaseModel):
    """A key-value assumption definition in a template."""

    key: str
    display_name: str
    category: str
    type: AssumptionType = AssumptionType.TEXT
    default_value: Any = None


class TemplateTable(BaseModel):
    """A table assumption definition in a template."""

    key: str
    display_name: str
    category: str
    columns: list[ColumnDef]


class TemplateCreate(BaseModel):
    """Request body for creating a template."""

    name: str
    description: str = ""
    key_values: list[TemplateKeyValue] = []
    tables: list[TemplateTable] = []


class TemplateResponse(BaseModel):
    """Template returned by the API."""

    id: str
    name: str
    description: str
    key_values: list[TemplateKeyValue]
    tables: list[TemplateTable]
    created_by: str
    created_at: datetime
    updated_at: datetime

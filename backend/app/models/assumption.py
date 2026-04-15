"""Pydantic models for assumptions."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class AssumptionType(StrEnum):
    """Supported assumption value types."""

    NUMBER = "number"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    DATE = "date"
    TEXT = "text"
    BOOLEAN = "boolean"


class AssumptionFormat(StrEnum):
    """Structure format of an assumption."""

    KEY_VALUE = "key_value"
    TABLE = "table"


class ColumnDef(BaseModel):
    """Column definition for table assumptions."""

    name: str
    type: AssumptionType = AssumptionType.TEXT


class AssumptionCreate(BaseModel):
    """Request body for creating an assumption."""

    key: str
    display_name: str
    category: str
    type: AssumptionType = AssumptionType.TEXT
    value: Any = None
    format: AssumptionFormat = AssumptionFormat.KEY_VALUE
    columns: list[ColumnDef] | None = None


class AssumptionUpdate(BaseModel):
    """Request body for updating an assumption."""

    display_name: str | None = None
    category: str | None = None
    value: Any = None
    columns: list[ColumnDef] | None = None


class AssumptionResponse(BaseModel):
    """Assumption returned by the API."""

    id: str
    key: str
    display_name: str
    category: str
    type: AssumptionType
    value: Any
    format: AssumptionFormat = AssumptionFormat.KEY_VALUE
    columns: list[ColumnDef] | None = None
    source_id: str | None = None
    is_overridden: bool = False
    version: int
    created_at: datetime
    updated_at: datetime


class HistoryEntry(BaseModel):
    """Single history entry for an assumption."""

    id: str
    version: int
    value: Any
    previous_value: Any
    changed_by: str
    changed_at: datetime
    reason: str | None = None


class TableRow(BaseModel):
    """A single row in a table assumption."""

    id: str = ""
    row_index: int = 0
    data: dict[str, Any] = {}


class TableRowCreate(BaseModel):
    """Request body for adding rows to a table assumption."""

    rows: list[dict[str, Any]]


class TableRowUpdate(BaseModel):
    """Request body for updating a single row."""

    data: dict[str, Any]


class AssumptionInDB(BaseModel):
    """Assumption as stored in Firestore."""

    key: str
    display_name: str
    category: str
    type: AssumptionType
    value: Any = None
    format: AssumptionFormat = AssumptionFormat.KEY_VALUE
    columns: list[dict[str, Any]] | None = None
    source_id: str | None = None
    is_overridden: bool = False
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_firestore(cls, doc_dict: dict[str, Any]) -> "AssumptionInDB":
        return cls(
            key=doc_dict.get("key", ""),
            display_name=doc_dict.get("display_name", ""),
            category=doc_dict.get("category", ""),
            type=doc_dict.get("type", "text"),
            value=doc_dict.get("value"),
            format=doc_dict.get("format", "key_value"),
            columns=doc_dict.get("columns"),
            source_id=doc_dict.get("source_id"),
            is_overridden=doc_dict.get("is_overridden", False),
            version=doc_dict.get("version", 1),
            created_at=doc_dict.get("created_at"),
            updated_at=doc_dict.get("updated_at"),
        )

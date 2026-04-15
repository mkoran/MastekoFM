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


class AssumptionCreate(BaseModel):
    """Request body for creating an assumption."""

    key: str
    display_name: str
    category: str
    type: AssumptionType
    value: Any


class AssumptionUpdate(BaseModel):
    """Request body for updating an assumption."""

    display_name: str | None = None
    category: str | None = None
    value: Any = None


class AssumptionResponse(BaseModel):
    """Assumption returned by the API."""

    id: str
    key: str
    display_name: str
    category: str
    type: AssumptionType
    value: Any
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


class AssumptionInDB(BaseModel):
    """Assumption as stored in Firestore."""

    key: str
    display_name: str
    category: str
    type: AssumptionType
    value: Any
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
            source_id=doc_dict.get("source_id"),
            is_overridden=doc_dict.get("is_overridden", False),
            version=doc_dict.get("version", 1),
            created_at=doc_dict.get("created_at"),
            updated_at=doc_dict.get("updated_at"),
        )

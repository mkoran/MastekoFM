"""Pydantic models for data sources."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class DataSourceType(StrEnum):
    """Supported data source types."""

    CSV = "csv"
    EXCEL = "excel"
    AIRTABLE = "airtable"
    MANUAL = "manual"


class FieldMapping(BaseModel):
    """Maps a source field to an assumption key."""

    source_field: str
    assumption_key: str
    transform: str | None = None


class DiscoveredField(BaseModel):
    """A field discovered from a data source."""

    name: str
    inferred_type: str
    sample_value: Any = None


class DataSourceCreate(BaseModel):
    """Request body for creating a data source."""

    name: str
    type: DataSourceType
    config: dict[str, Any] = {}


class DataSourceUpdate(BaseModel):
    """Request body for updating a data source."""

    name: str | None = None
    config: dict[str, Any] | None = None
    field_mappings: list[FieldMapping] | None = None


class DataSourceResponse(BaseModel):
    """Data source returned by the API."""

    id: str
    name: str
    type: DataSourceType
    config: dict[str, Any]
    field_mappings: list[FieldMapping]
    sync_status: str
    last_synced_at: datetime | None = None
    sync_error: str | None = None
    created_at: datetime
    updated_at: datetime


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    synced_count: int = 0
    error_count: int = 0
    errors: list[str] = []


class DataSourceInDB(BaseModel):
    """Data source as stored in Firestore."""

    name: str
    type: DataSourceType
    config: dict[str, Any] = {}
    field_mappings: list[dict[str, Any]] = []
    sync_status: str = "idle"
    last_synced_at: datetime | None = None
    sync_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_firestore(cls, doc_dict: dict[str, Any]) -> "DataSourceInDB":
        return cls(
            name=doc_dict.get("name", ""),
            type=doc_dict.get("type", "manual"),
            config=doc_dict.get("config", {}),
            field_mappings=doc_dict.get("field_mappings", []),
            sync_status=doc_dict.get("sync_status", "idle"),
            last_synced_at=doc_dict.get("last_synced_at"),
            sync_error=doc_dict.get("sync_error"),
            created_at=doc_dict.get("created_at"),
            updated_at=doc_dict.get("updated_at"),
        )

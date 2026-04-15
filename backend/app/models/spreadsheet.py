"""Pydantic models for spreadsheets (calculation nodes)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SpreadsheetUpload(BaseModel):
    """Request to register a spreadsheet template."""

    name: str
    description: str = ""


class CellMapping(BaseModel):
    """Maps an assumption key to a cell in the spreadsheet."""

    assumption_key: str
    sheet_name: str
    cell_ref: str


class OutputExtraction(BaseModel):
    """Defines what to extract from a calculated spreadsheet."""

    sheet_name: str
    extraction_type: str = "table"  # "table" or "cell"
    start_row: int = 1
    end_row: int = 100
    columns: dict[str, str] = {}  # {"A": "label", "B": "value"}
    cells: list[str] = []  # for cell type: ["B5", "B6"]


class SpreadsheetResponse(BaseModel):
    """Spreadsheet node returned by the API."""

    id: str
    project_id: str
    name: str
    description: str
    file_stored: bool = False
    input_mappings: list[CellMapping] = []
    output_extractions: list[dict[str, Any]] = []
    last_calculated_at: datetime | None = None
    calculation_status: str = "idle"
    cached_outputs: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

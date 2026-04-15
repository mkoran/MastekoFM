"""Pydantic models for DAG (directed acyclic graph)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DAGNode(BaseModel):
    """A node in the calculation DAG (represents a spreadsheet)."""

    id: str
    spreadsheet_id: str
    name: str
    position: dict[str, float] = {"x": 0, "y": 0}
    status: str = "idle"  # idle, calculating, done, error, stale


class DAGEdge(BaseModel):
    """An edge connecting two DAG nodes (output → input mapping)."""

    id: str
    source_node_id: str
    source_output_key: str
    target_node_id: str
    target_input_key: str


class DAGResponse(BaseModel):
    """Full DAG state for a project."""

    project_id: str
    nodes: list[DAGNode] = []
    edges: list[DAGEdge] = []
    last_calculated_at: datetime | None = None


class CalculationResult(BaseModel):
    """Result of a DAG calculation."""

    success: bool
    nodes_calculated: int = 0
    errors: list[str] = []
    outputs: dict[str, Any] = {}

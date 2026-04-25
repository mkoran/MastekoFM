"""Pydantic models for Projects (thin org scope post-Sprint-B redesign).

A Project is no longer bound 1:1 to a Model. It's an organizational scope:
- Drive folder root
- members + roles (Sprint E)
- optional default_model_id (just for UX convenience in the New Run modal)

Runs reference Project + AssumptionPack + Model + OutputTemplate independently.
"""
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Request body for creating a Project."""

    name: str
    code_name: str = ""
    description: str = ""
    default_model_id: str | None = None  # optional pre-selected Model in the New Run modal


class ProjectUpdate(BaseModel):
    """Request body for updating a Project."""

    name: str | None = None
    code_name: str | None = None
    description: str | None = None
    default_model_id: str | None = None
    status: str | None = None  # "active" | "archived"
    archived: bool | None = None  # Sprint UX-01: explicit archive boolean


class ProjectResponse(BaseModel):
    """Project record."""

    id: str
    name: str
    code_name: str
    description: str
    default_model_id: str | None = None
    default_model_name: str | None = None
    default_model_version: int | None = None
    status: str
    archived: bool = False  # Sprint UX-01: explicit boolean alongside status string
    drive_folder_url: str | None = None  # Sprint UX-01: link to project Drive folder
    created_by: str
    created_by_email: str | None = None  # Sprint UX-01: denormalized for "Created By" column
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    """List-view summary for Projects."""

    id: str
    name: str
    code_name: str
    default_model_id: str | None = None
    default_model_name: str | None = None
    status: str
    archived: bool = False
    drive_folder_url: str | None = None
    pack_count: int = 0
    run_count: int = 0  # Sprint UX-01: count of Runs for this project
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_by: str = ""
    created_by_email: str | None = None
    created_at: datetime

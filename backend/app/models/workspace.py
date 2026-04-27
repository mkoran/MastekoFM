"""Sprint G1 — Workspace entity.

A Workspace sits above Projects. It's the unit a person belongs to and
(future) the unit of permission. A user can be a member of multiple
workspaces. Each workspace has its own Drive folder containing all of its
Models, OutputTemplates, and Projects.

Permissions are deferred — `members` is recorded today but not enforced;
any authenticated user can read/write any workspace until role-based
checks land in a separate sprint.
"""
from datetime import datetime

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    """Request body for creating a Workspace."""

    name: str
    code_name: str = ""
    description: str = ""


class WorkspaceUpdate(BaseModel):
    """Request body for updating a Workspace."""

    name: str | None = None
    description: str | None = None
    archived: bool | None = None
    members_add: list[str] | None = None  # user uids to add
    members_remove: list[str] | None = None  # user uids to remove


class WorkspaceResponse(BaseModel):
    """Workspace record."""

    id: str
    name: str
    code_name: str
    description: str
    members: list[str]
    member_count: int = 0
    drive_folder_id: str | None = None
    drive_folder_url: str | None = None
    archived: bool = False
    created_by: str
    created_by_email: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkspaceSummary(BaseModel):
    """List-view summary."""

    id: str
    name: str
    code_name: str
    member_count: int = 0
    project_count: int = 0
    drive_folder_url: str | None = None
    archived: bool = False
    created_at: datetime

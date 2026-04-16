"""Pydantic models for projects."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Checkout(BaseModel):
    """Project checkout (lock) state."""

    user_uid: str | None = None
    user_name: str | None = None
    checked_out_at: datetime | None = None
    expires_at: datetime | None = None


class ProjectCreate(BaseModel):
    """Request body for creating a project."""

    name: str
    code_name: str = ""
    template_group_id: str | None = None


class ProjectUpdate(BaseModel):
    """Request body for updating a project."""

    name: str | None = None
    code_name: str | None = None
    template_group_id: str | None = None


class ProjectResponse(BaseModel):
    """Project returned by the API."""

    id: str
    name: str
    code_name: str
    owner_uid: str
    status: str
    template_group_id: str | None = None
    template_group_name: str | None = None
    checkout: Checkout
    created_at: datetime
    updated_at: datetime


class ProjectInDB(BaseModel):
    """Project document as stored in Firestore."""

    name: str
    code_name: str = ""
    owner_uid: str
    status: str = "active"
    template_group_id: str | None = None
    template_group_name: str | None = None
    checkout: Checkout = Checkout()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    drive_folder_id: str | None = None

    @classmethod
    def from_firestore(cls, doc_dict: dict[str, Any]) -> "ProjectInDB":
        """Create from Firestore document, tolerating missing fields."""
        checkout_data = doc_dict.get("checkout", {}) or {}
        return cls(
            name=doc_dict.get("name", ""),
            code_name=doc_dict.get("code_name", "") or "",
            owner_uid=doc_dict.get("owner_uid", ""),
            status=doc_dict.get("status", "active"),
            template_group_id=doc_dict.get("template_group_id"),
            template_group_name=doc_dict.get("template_group_name"),
            checkout=Checkout(**checkout_data) if checkout_data else Checkout(),
            created_at=doc_dict.get("created_at"),
            updated_at=doc_dict.get("updated_at"),
            drive_folder_id=doc_dict.get("drive_folder_id"),
        )

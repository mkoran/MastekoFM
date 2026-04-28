"""Sprint I-2 — Workspace-level external-system connections.

A Connection is a stored credential + metadata for talking to an external
data source on behalf of a workspace. Today the only kind is Airtable;
Sprint I-3 will add QBO.

Living under workspaces (subcollection ``workspaces/{ws}/connections/{id}``)
means every member of the workspace can use a connection to fill packs,
without each person re-doing OAuth. Secrets are KMS-encrypted at rest
(reuses Sprint F's secrets service).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConnectionCreate(BaseModel):
    """Body for POST /api/workspaces/{ws}/connections.

    The ``secret`` field is the raw API key / token. The backend KMS-encrypts
    it before writing to Firestore — it is NEVER returned by any endpoint.
    """

    name: str
    kind: Literal["airtable"]   # Sprint I-3 adds "qbo"
    secret: str                 # raw API key (Airtable: PAT or legacy key)
    metadata: dict[str, str] = {}  # base_id, etc.


class ConnectionUpdate(BaseModel):
    """Edit a connection. Pass ``secret`` only when rotating the key."""

    name: str | None = None
    secret: str | None = None
    metadata: dict[str, str] | None = None


class ConnectionResponse(BaseModel):
    """Public-facing shape — secret is intentionally never included."""

    id: str
    workspace_id: str
    name: str
    kind: Literal["airtable"]
    metadata: dict[str, str] = {}
    has_secret: bool = True
    created_by_email: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionSummary(BaseModel):
    """Small list-view shape for dropdowns in the pack source UI."""

    id: str
    name: str
    kind: Literal["airtable"]
    metadata: dict[str, str] = {}

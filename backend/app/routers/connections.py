"""Sprint I-2 — workspace-level external connections (Airtable + later QBO).

Endpoints (all require auth; Sprint J will add per-workspace permission gates):

  GET    /api/workspaces/{ws_id}/connections
  POST   /api/workspaces/{ws_id}/connections
  GET    /api/workspaces/{ws_id}/connections/{conn_id}
  PUT    /api/workspaces/{ws_id}/connections/{conn_id}
  DELETE /api/workspaces/{ws_id}/connections/{conn_id}

The connection's secret (Airtable PAT) is KMS-encrypted on write and
NEVER returned by any GET — clients only see ``has_secret: true``.
Rotating the secret is a PUT with a new ``secret`` field.
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.connection import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionSummary,
    ConnectionUpdate,
)
from backend.app.services import secrets as secrets_svc

router = APIRouter(tags=["connections"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _conn_ref(workspace_id: str):
    prefix = settings.firestore_collection_prefix
    return (
        get_firestore_client()
        .collection(f"{prefix}workspaces")
        .document(workspace_id)
        .collection("connections")
    )


def _to_response(workspace_id: str, doc_id: str, data: dict[str, Any]) -> ConnectionResponse:
    return ConnectionResponse(
        id=doc_id,
        workspace_id=workspace_id,
        name=data.get("name", ""),
        kind=data.get("kind", "airtable"),
        metadata=data.get("metadata", {}),
        has_secret=bool(data.get("secret_encrypted")),
        created_by_email=data.get("created_by_email"),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


def _to_summary(doc_id: str, data: dict[str, Any]) -> ConnectionSummary:
    return ConnectionSummary(
        id=doc_id,
        name=data.get("name", ""),
        kind=data.get("kind", "airtable"),
        metadata=data.get("metadata", {}),
    )


@router.get(
    "/api/workspaces/{ws_id}/connections",
    response_model=list[ConnectionSummary],
)
async def list_connections(ws_id: str, current_user: CurrentUser):
    return [_to_summary(d.id, d.to_dict() or {}) for d in _conn_ref(ws_id).stream()]


@router.post(
    "/api/workspaces/{ws_id}/connections",
    response_model=ConnectionResponse,
    status_code=201,
)
async def create_connection(
    ws_id: str, body: ConnectionCreate, current_user: CurrentUser,
):
    if not body.secret:
        raise HTTPException(status_code=400, detail="secret is required")
    try:
        secret_encrypted = secrets_svc.encrypt(body.secret)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=(
                "KMS encryption unavailable. Make sure the KMS key is configured "
                f"and the runtime SA has cloudkms.encrypt: {exc}"
            ),
        ) from exc

    now = datetime.now(UTC)
    data = {
        "workspace_id": ws_id,
        "name": body.name,
        "kind": body.kind,
        "metadata": body.metadata or {},
        "secret_encrypted": secret_encrypted,
        "created_by": current_user["uid"],
        "created_by_email": current_user.get("email", ""),
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = _conn_ref(ws_id).document()
    doc_ref.set(data)
    return _to_response(ws_id, doc_ref.id, data)


@router.get(
    "/api/workspaces/{ws_id}/connections/{conn_id}",
    response_model=ConnectionResponse,
)
async def get_connection(ws_id: str, conn_id: str, current_user: CurrentUser):
    snap = _conn_ref(ws_id).document(conn_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _to_response(ws_id, conn_id, snap.to_dict() or {})


@router.put(
    "/api/workspaces/{ws_id}/connections/{conn_id}",
    response_model=ConnectionResponse,
)
async def update_connection(
    ws_id: str, conn_id: str, body: ConnectionUpdate, current_user: CurrentUser,
):
    doc_ref = _conn_ref(ws_id).document(conn_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Connection not found")
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.metadata is not None:
        updates["metadata"] = body.metadata
    if body.secret is not None:
        if not body.secret:
            raise HTTPException(status_code=400, detail="secret cannot be empty when provided")
        try:
            updates["secret_encrypted"] = secrets_svc.encrypt(body.secret)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"KMS encrypt failed: {exc}") from exc
    doc_ref.update(updates)
    return _to_response(ws_id, conn_id, {**snap.to_dict(), **updates})


@router.delete(
    "/api/workspaces/{ws_id}/connections/{conn_id}",
    status_code=204,
)
async def delete_connection(ws_id: str, conn_id: str, current_user: CurrentUser):
    doc_ref = _conn_ref(ws_id).document(conn_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Connection not found")
    doc_ref.delete()
    return None

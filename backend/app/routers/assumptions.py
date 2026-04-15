"""Assumptions router — CRUD, versioning, history."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.assumption import AssumptionCreate, AssumptionResponse, AssumptionUpdate, HistoryEntry
from backend.app.services.assumption_engine import validate_assumption_value

router = APIRouter(prefix="/api/projects/{project_id}/assumptions", tags=["assumptions"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _assumptions_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id).collection("assumptions")


def _to_response(doc_id: str, data: dict[str, Any]) -> AssumptionResponse:
    return AssumptionResponse(
        id=doc_id,
        key=data.get("key", ""),
        display_name=data.get("display_name", ""),
        category=data.get("category", ""),
        type=data.get("type", "text"),
        value=data.get("value"),
        source_id=data.get("source_id"),
        is_overridden=data.get("is_overridden", False),
        version=data.get("version", 1),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.post("", response_model=AssumptionResponse, status_code=201)
async def create_assumption(project_id: str, body: AssumptionCreate, current_user: CurrentUser):
    """Create a new assumption."""
    validated_value = validate_assumption_value(body.type, body.value)
    now = datetime.now(UTC)
    data = {
        "key": body.key,
        "display_name": body.display_name,
        "category": body.category,
        "type": body.type.value,
        "value": validated_value,
        "source_id": None,
        "is_overridden": False,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = _assumptions_ref(project_id).document()
    doc_ref.set(data)

    # Create initial history entry
    doc_ref.collection("history").add({
        "version": 1,
        "value": validated_value,
        "previous_value": None,
        "changed_by": current_user["uid"],
        "changed_at": now,
        "reason": "Created",
    })

    return _to_response(doc_ref.id, data)


@router.get("", response_model=list[AssumptionResponse])
async def list_assumptions(project_id: str, current_user: CurrentUser, category: str | None = None):
    """List assumptions for a project, optionally filtered by category."""
    ref = _assumptions_ref(project_id)
    query = ref.where("category", "==", category) if category else ref
    docs = query.stream()
    return [_to_response(doc.id, doc.to_dict()) for doc in docs]


@router.get("/{assumption_id}", response_model=AssumptionResponse)
async def get_assumption(project_id: str, assumption_id: str, current_user: CurrentUser):
    """Get a single assumption."""
    doc = _assumptions_ref(project_id).document(assumption_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Assumption not found")
    return _to_response(doc.id, doc.to_dict())


@router.put("/{assumption_id}", response_model=AssumptionResponse)
async def update_assumption(
    project_id: str, assumption_id: str, body: AssumptionUpdate, current_user: CurrentUser
):
    """Update an assumption. Creates a history entry on every value change."""
    doc_ref = _assumptions_ref(project_id).document(assumption_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Assumption not found")

    data = doc.to_dict()
    now = datetime.now(UTC)
    updates: dict[str, Any] = {"updated_at": now}

    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.category is not None:
        updates["category"] = body.category

    # Value change triggers history entry
    if body.value is not None:
        old_value = data.get("value")
        new_value = validate_assumption_value(data["type"], body.value)
        updates["value"] = new_value
        new_version = data.get("version", 1) + 1
        updates["version"] = new_version

        # History entry — every value change, no exceptions (CLAUDE.md)
        doc_ref.collection("history").add({
            "version": new_version,
            "value": new_value,
            "previous_value": old_value,
            "changed_by": current_user["uid"],
            "changed_at": now,
            "reason": "Manual edit",
        })

    doc_ref.update(updates)
    return _to_response(assumption_id, {**data, **updates})


@router.delete("/{assumption_id}", status_code=204)
async def delete_assumption(project_id: str, assumption_id: str, current_user: CurrentUser):
    """Delete an assumption."""
    doc_ref = _assumptions_ref(project_id).document(assumption_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Assumption not found")
    doc_ref.delete()


@router.get("/{assumption_id}/history", response_model=list[HistoryEntry])
async def get_history(project_id: str, assumption_id: str, current_user: CurrentUser):
    """Get assumption change history."""
    doc_ref = _assumptions_ref(project_id).document(assumption_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Assumption not found")

    history_docs = doc_ref.collection("history").order_by("version").stream()
    return [
        HistoryEntry(
            id=h.id,
            version=h.to_dict().get("version", 0),
            value=h.to_dict().get("value"),
            previous_value=h.to_dict().get("previous_value"),
            changed_by=h.to_dict().get("changed_by", ""),
            changed_at=h.to_dict().get("changed_at", datetime.now(UTC)),
            reason=h.to_dict().get("reason"),
        )
        for h in history_docs
    ]

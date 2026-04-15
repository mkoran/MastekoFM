"""Assumptions router — CRUD, versioning, history, table rows."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.assumption import (
    AssumptionCreate,
    AssumptionResponse,
    AssumptionUpdate,
    HistoryEntry,
    TableRow,
    TableRowCreate,
    TableRowUpdate,
)
from backend.app.services.assumption_engine import validate_assumption_value

router = APIRouter(prefix="/api/projects/{project_id}/assumptions", tags=["assumptions"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _assumptions_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id).collection("assumptions")


def _to_response(doc_id: str, data: dict[str, Any]) -> AssumptionResponse:
    columns = data.get("columns")
    return AssumptionResponse(
        id=doc_id,
        key=data.get("key", ""),
        display_name=data.get("display_name", ""),
        category=data.get("category", ""),
        type=data.get("type", "text"),
        value=data.get("value"),
        format=data.get("format", "key_value"),
        columns=columns,
        source_id=data.get("source_id"),
        is_overridden=data.get("is_overridden", False),
        version=data.get("version", 1),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


# ─── Key-value + Table assumption CRUD ───

@router.post("", response_model=AssumptionResponse, status_code=201)
async def create_assumption(project_id: str, body: AssumptionCreate, current_user: CurrentUser):
    """Create a new assumption (key_value or table)."""
    now = datetime.now(UTC)
    data: dict[str, Any] = {
        "key": body.key,
        "display_name": body.display_name,
        "category": body.category,
        "type": body.type.value,
        "format": body.format.value,
        "source_id": None,
        "is_overridden": False,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }

    if body.format == "table":
        data["value"] = None
        data["columns"] = [c.model_dump() for c in (body.columns or [])]
    else:
        data["value"] = validate_assumption_value(body.type, body.value)
        data["columns"] = None

    doc_ref = _assumptions_ref(project_id).document()
    doc_ref.set(data)

    doc_ref.collection("history").add({
        "version": 1,
        "value": data.get("value"),
        "previous_value": None,
        "changed_by": current_user["uid"],
        "changed_at": now,
        "reason": "Created",
    })

    return _to_response(doc_ref.id, data)


@router.get("", response_model=list[AssumptionResponse])
async def list_assumptions(project_id: str, current_user: CurrentUser, category: str | None = None):
    """List assumptions, optionally filtered by category."""
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
    """Update an assumption. Creates history entry on value changes."""
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
    if body.columns is not None:
        updates["columns"] = [c.model_dump() for c in body.columns]

    if body.value is not None:
        old_value = data.get("value")
        new_value = validate_assumption_value(data["type"], body.value)
        updates["value"] = new_value
        new_version = data.get("version", 1) + 1
        updates["version"] = new_version

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


# ─── Table row CRUD ───

@router.get("/{assumption_id}/rows", response_model=list[TableRow])
async def list_rows(project_id: str, assumption_id: str, current_user: CurrentUser):
    """List rows for a table assumption."""
    doc = _assumptions_ref(project_id).document(assumption_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Assumption not found")
    if doc.to_dict().get("format") != "table":
        raise HTTPException(status_code=400, detail="Not a table assumption")

    rows_ref = _assumptions_ref(project_id).document(assumption_id).collection("rows")
    docs = rows_ref.order_by("row_index").stream()
    return [
        TableRow(id=d.id, row_index=d.to_dict().get("row_index", 0), data=d.to_dict().get("data", {}))
        for d in docs
    ]


@router.post("/{assumption_id}/rows", response_model=list[TableRow], status_code=201)
async def add_rows(
    project_id: str, assumption_id: str, body: TableRowCreate, current_user: CurrentUser
):
    """Add rows to a table assumption (batch)."""
    doc_ref = _assumptions_ref(project_id).document(assumption_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Assumption not found")
    if doc.to_dict().get("format") != "table":
        raise HTTPException(status_code=400, detail="Not a table assumption")

    rows_ref = doc_ref.collection("rows")

    # Get current max row_index
    existing = list(rows_ref.order_by("row_index", direction="DESCENDING").limit(1).stream())
    next_index = (existing[0].to_dict().get("row_index", 0) + 1) if existing else 0

    result = []
    for i, row_data in enumerate(body.rows):
        row_doc = rows_ref.document()
        row_record = {"row_index": next_index + i, "data": row_data}
        row_doc.set(row_record)
        result.append(TableRow(id=row_doc.id, row_index=next_index + i, data=row_data))

    # Update version
    now = datetime.now(UTC)
    new_version = doc.to_dict().get("version", 1) + 1
    doc_ref.update({"version": new_version, "updated_at": now})

    return result


@router.put("/{assumption_id}/rows/{row_id}", response_model=TableRow)
async def update_row(
    project_id: str, assumption_id: str, row_id: str, body: TableRowUpdate, current_user: CurrentUser
):
    """Update a single row in a table assumption."""
    row_ref = _assumptions_ref(project_id).document(assumption_id).collection("rows").document(row_id)
    row_doc = row_ref.get()
    if not row_doc.exists:
        raise HTTPException(status_code=404, detail="Row not found")

    row_ref.update({"data": body.data})
    updated = row_doc.to_dict()
    updated["data"] = body.data

    # Bump assumption version
    doc_ref = _assumptions_ref(project_id).document(assumption_id)
    now = datetime.now(UTC)
    new_version = doc_ref.get().to_dict().get("version", 1) + 1
    doc_ref.update({"version": new_version, "updated_at": now})

    return TableRow(id=row_id, row_index=updated.get("row_index", 0), data=body.data)


@router.delete("/{assumption_id}/rows/{row_id}", status_code=204)
async def delete_row(
    project_id: str, assumption_id: str, row_id: str, current_user: CurrentUser
):
    """Delete a row from a table assumption."""
    row_ref = _assumptions_ref(project_id).document(assumption_id).collection("rows").document(row_id)
    row_doc = row_ref.get()
    if not row_doc.exists:
        raise HTTPException(status_code=404, detail="Row not found")
    row_ref.delete()

"""Data sources router — CRUD, field discovery, sync."""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.datasource import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    DiscoveredField,
    FieldMapping,
    SyncResult,
)

router = APIRouter(prefix="/api/projects/{project_id}/datasources", tags=["datasources"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _datasources_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id).collection("datasources")


def _to_response(doc_id: str, data: dict[str, Any]) -> DataSourceResponse:
    mappings = [FieldMapping(**m) if isinstance(m, dict) else m for m in data.get("field_mappings", [])]
    return DataSourceResponse(
        id=doc_id,
        name=data.get("name", ""),
        type=data.get("type", "manual"),
        config=data.get("config", {}),
        field_mappings=mappings,
        sync_status=data.get("sync_status", "idle"),
        last_synced_at=data.get("last_synced_at"),
        sync_error=data.get("sync_error"),
        created_at=data.get("created_at", datetime.now(UTC)),
        updated_at=data.get("updated_at", datetime.now(UTC)),
    )


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_datasource(project_id: str, body: DataSourceCreate, current_user: CurrentUser):
    """Create a new data source."""
    now = datetime.now(UTC)
    data = {
        "name": body.name,
        "type": body.type.value,
        "config": body.config,
        "field_mappings": [],
        "sync_status": "idle",
        "last_synced_at": None,
        "sync_error": None,
        "created_at": now,
        "updated_at": now,
    }
    doc_ref = _datasources_ref(project_id).document()
    doc_ref.set(data)
    return _to_response(doc_ref.id, data)


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(project_id: str, current_user: CurrentUser):
    """List data sources for a project."""
    docs = _datasources_ref(project_id).stream()
    return [_to_response(doc.id, doc.to_dict()) for doc in docs]


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_datasource(project_id: str, source_id: str, current_user: CurrentUser):
    """Get a single data source."""
    doc = _datasources_ref(project_id).document(source_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _to_response(doc.id, doc.to_dict())


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_datasource(
    project_id: str, source_id: str, body: DataSourceUpdate, current_user: CurrentUser
):
    """Update a data source."""
    doc_ref = _datasources_ref(project_id).document(source_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Data source not found")

    data = doc.to_dict()
    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        updates["name"] = body.name
    if body.config is not None:
        updates["config"] = body.config
    if body.field_mappings is not None:
        updates["field_mappings"] = [m.model_dump() for m in body.field_mappings]

    doc_ref.update(updates)
    return _to_response(source_id, {**data, **updates})


@router.delete("/{source_id}", status_code=204)
async def delete_datasource(project_id: str, source_id: str, current_user: CurrentUser):
    """Delete a data source."""
    doc_ref = _datasources_ref(project_id).document(source_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Data source not found")
    doc_ref.delete()


@router.post("/{source_id}/discover", response_model=list[DiscoveredField])
async def discover_fields(
    project_id: str,
    source_id: str,
    current_user: CurrentUser,
    file: UploadFile | None = None,
):
    """Discover available fields from a data source."""
    doc = _datasources_ref(project_id).document(source_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Data source not found")

    data = doc.to_dict()
    source_type = data.get("type", "")
    config = data.get("config", {})

    if source_type == "csv":
        from backend.app.connectors.csv_connector import discover_fields as csv_discover

        if file:
            content = await file.read()
        elif config.get("file_content_b64"):
            import base64

            content = base64.b64decode(config["file_content_b64"])
        else:
            raise HTTPException(status_code=400, detail="CSV file required")
        return csv_discover(content)

    if source_type == "excel":
        from backend.app.connectors.excel_connector import discover_fields as excel_discover

        if file:
            content = await file.read()
        elif config.get("file_content_b64"):
            import base64

            content = base64.b64decode(config["file_content_b64"])
        else:
            raise HTTPException(status_code=400, detail="Excel file required")
        return excel_discover(content, config.get("sheet_name"))

    if source_type == "airtable":
        from backend.app.connectors.airtable import discover_fields as at_discover

        base_id = config.get("base_id")
        table_name = config.get("table_name")
        api_key = config.get("api_key")
        if not all([base_id, table_name, api_key]):
            raise HTTPException(status_code=400, detail="Airtable config requires base_id, table_name, api_key")
        return at_discover(base_id, table_name, api_key)

    raise HTTPException(status_code=400, detail=f"Unsupported source type: {source_type}")


@router.post("/{source_id}/sync", response_model=SyncResult)
async def sync_datasource_endpoint(project_id: str, source_id: str, current_user: CurrentUser):
    """Trigger a sync for a data source."""
    doc_ref = _datasources_ref(project_id).document(source_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Data source not found")

    data = doc.to_dict()
    source_type = data.get("type", "")
    config = data.get("config", {})
    field_mappings = data.get("field_mappings", [])

    if not field_mappings:
        raise HTTPException(status_code=400, detail="No field mappings configured")

    # Mark as syncing
    doc_ref.update({"sync_status": "syncing", "sync_error": None})

    try:
        # Fetch raw data from connector
        mappings = [FieldMapping(**m) for m in field_mappings]
        raw_data: dict[str, Any] = {}

        if source_type == "csv":
            import base64

            from backend.app.connectors.csv_connector import fetch_data as csv_fetch

            content = base64.b64decode(config.get("file_content_b64", ""))
            raw_data = csv_fetch(content, mappings)

        elif source_type == "excel":
            import base64

            from backend.app.connectors.excel_connector import fetch_data as excel_fetch

            content = base64.b64decode(config.get("file_content_b64", ""))
            raw_data = excel_fetch(content, mappings, config.get("sheet_name"))

        elif source_type == "airtable":
            from backend.app.connectors.airtable import fetch_data as at_fetch

            raw_data = at_fetch(config["base_id"], config["table_name"], config["api_key"], mappings)

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source type: {source_type}")

        # Sync to assumptions
        from backend.app.services.datasource_sync import sync_datasource

        result = sync_datasource(project_id, source_id, source_type, field_mappings, raw_data, current_user)

        now = datetime.now(UTC)
        doc_ref.update({
            "sync_status": "idle" if result["success"] else "error",
            "last_synced_at": now,
            "sync_error": "; ".join(result["errors"]) if result["errors"] else None,
            "updated_at": now,
        })

        return SyncResult(**result)

    except HTTPException:
        raise
    except Exception as e:
        doc_ref.update({"sync_status": "error", "sync_error": str(e)})
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}") from e

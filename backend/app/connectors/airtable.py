"""Airtable connector — field discovery and data fetch via Airtable API."""
import json
import logging
import urllib.request
from typing import Any

from backend.app.models.datasource import DiscoveredField, FieldMapping
from backend.app.services.datasource_sync import infer_field_type

logger = logging.getLogger(__name__)

AIRTABLE_API_BASE = "https://api.airtable.com/v0"


def _airtable_request(url: str, api_key: str) -> dict[str, Any]:
    """Make an authenticated GET request to the Airtable API."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read())


def discover_fields(base_id: str, table_name: str, api_key: str) -> list[DiscoveredField]:
    """Discover fields by fetching the first few records from an Airtable table."""
    url = f"{AIRTABLE_API_BASE}/{base_id}/{urllib.request.quote(table_name)}?maxRecords=5"
    data = _airtable_request(url, api_key)

    records = data.get("records", [])
    if not records:
        return []

    # Collect all field names and sample values
    all_fields: dict[str, list[Any]] = {}
    for record in records:
        fields = record.get("fields", {})
        for name, value in fields.items():
            all_fields.setdefault(name, []).append(value)

    return [
        DiscoveredField(
            name=name,
            inferred_type=infer_field_type(values),
            sample_value=values[0] if values else None,
        )
        for name, values in all_fields.items()
    ]


def fetch_data(
    base_id: str, table_name: str, api_key: str, mappings: list[FieldMapping]
) -> dict[str, Any]:
    """Fetch mapped field values from the first Airtable record."""
    url = f"{AIRTABLE_API_BASE}/{base_id}/{urllib.request.quote(table_name)}?maxRecords=1"
    data = _airtable_request(url, api_key)

    records = data.get("records", [])
    if not records:
        return {}

    fields = records[0].get("fields", {})
    result: dict[str, Any] = {}
    for mapping in mappings:
        if mapping.source_field in fields:
            result[mapping.source_field] = fields[mapping.source_field]
    return result

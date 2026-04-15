"""CSV connector — parse CSV files and discover fields."""
import csv
import io
from typing import Any

from backend.app.models.datasource import DiscoveredField, FieldMapping
from backend.app.services.datasource_sync import infer_field_type


def parse_csv(file_content: bytes) -> list[dict[str, Any]]:
    """Parse CSV content into a list of row dicts. First row = headers."""
    text = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def discover_fields(file_content: bytes) -> list[DiscoveredField]:
    """Discover fields from CSV: headers, inferred types, sample values."""
    rows = parse_csv(file_content)
    if not rows:
        return []

    headers = list(rows[0].keys())
    fields = []
    for header in headers:
        values = [row.get(header) for row in rows[:20]]
        fields.append(DiscoveredField(
            name=header,
            inferred_type=infer_field_type(values),
            sample_value=values[0] if values else None,
        ))
    return fields


def fetch_data(file_content: bytes, mappings: list[FieldMapping]) -> dict[str, Any]:
    """Extract mapped values from CSV (uses first data row)."""
    rows = parse_csv(file_content)
    if not rows:
        return {}

    row = rows[0]
    result: dict[str, Any] = {}
    for mapping in mappings:
        if mapping.source_field in row:
            result[mapping.source_field] = row[mapping.source_field]
    return result

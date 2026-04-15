"""Data source sync service — orchestration and type inference."""
import logging
import re
from datetime import UTC, datetime
from typing import Any

from backend.app.models.assumption import AssumptionType

logger = logging.getLogger(__name__)


def infer_field_type(values: list[Any]) -> str:
    """Infer the assumption type from a list of sample values.

    Returns an AssumptionType string. Defaults to "text" when uncertain.
    """
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return AssumptionType.TEXT

    # Check boolean
    bool_values = {"true", "false", "yes", "no", "1", "0"}
    if all(str(v).strip().lower() in bool_values for v in non_null):
        return AssumptionType.BOOLEAN

    # Check percentage (ends with %)
    if all(str(v).strip().endswith("%") for v in non_null):
        return AssumptionType.PERCENTAGE

    # Check currency (starts with $ or contains comma-separated digits)
    currency_pattern = re.compile(r"^\$[\d,]+\.?\d*$")
    if all(currency_pattern.match(str(v).strip()) for v in non_null):
        return AssumptionType.CURRENCY

    # Check numeric
    def is_numeric(v: Any) -> bool:
        try:
            float(str(v).replace(",", ""))
            return True
        except (ValueError, TypeError):
            return False

    if all(is_numeric(v) for v in non_null):
        return AssumptionType.NUMBER

    # Check date (ISO format or common patterns)
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}")
    if all(date_pattern.match(str(v).strip()) for v in non_null):
        return AssumptionType.DATE

    return AssumptionType.TEXT


def coerce_value(value: Any, field_type: str) -> Any:
    """Coerce a raw value to the target type."""
    if value is None:
        return None

    s = str(value).strip()

    match field_type:
        case "number":
            try:
                return float(s.replace(",", ""))
            except (ValueError, TypeError):
                return None
        case "currency":
            try:
                return float(s.replace("$", "").replace(",", ""))
            except (ValueError, TypeError):
                return None
        case "percentage":
            try:
                v = float(s.rstrip("%").replace(",", ""))
                return v / 100 if v > 1 else v
            except (ValueError, TypeError):
                return None
        case "boolean":
            return s.lower() in ("true", "yes", "1")
        case "date":
            return s
        case _:
            return s


def sync_datasource(
    project_id: str,
    source_id: str,
    source_type: str,
    field_mappings: list[dict[str, Any]],
    raw_data: dict[str, Any],
    current_user: dict[str, Any],
) -> dict[str, Any]:
    """Sync raw data from a connector into assumptions.

    Returns a SyncResult-compatible dict.
    """
    from backend.app.config import get_firestore_client, settings
    from backend.app.services.assumption_engine import validate_assumption_value

    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix
    assumptions_ref = db.collection(f"{prefix}projects").document(project_id).collection("assumptions")

    synced = 0
    errors: list[str] = []

    for mapping in field_mappings:
        source_field = mapping.get("source_field", "")
        assumption_key = mapping.get("assumption_key", "")

        if source_field not in raw_data:
            errors.append(f"Field '{source_field}' not found in source data")
            continue

        raw_value = raw_data[source_field]

        try:
            # Find existing assumption by key
            existing = list(assumptions_ref.where("key", "==", assumption_key).limit(1).stream())

            now = datetime.now(UTC)

            if existing:
                doc = existing[0]
                doc_data = doc.to_dict()
                assumption_type = doc_data.get("type", "text")
                validated = validate_assumption_value(assumption_type, raw_value)
                old_value = doc_data.get("value")
                new_version = doc_data.get("version", 1) + 1

                doc.reference.update({
                    "value": validated,
                    "version": new_version,
                    "source_id": source_id,
                    "updated_at": now,
                })
                doc.reference.collection("history").add({
                    "version": new_version,
                    "value": validated,
                    "previous_value": old_value,
                    "changed_by": current_user["uid"],
                    "changed_at": now,
                    "reason": f"{source_type} sync",
                })
            else:
                # Create new assumption from source
                inferred = infer_field_type([raw_value])
                validated = validate_assumption_value(inferred, raw_value)
                doc_ref = assumptions_ref.document()
                doc_ref.set({
                    "key": assumption_key,
                    "display_name": assumption_key.replace("_", " ").title(),
                    "category": "Imported",
                    "type": inferred,
                    "value": validated,
                    "source_id": source_id,
                    "is_overridden": False,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                })
                doc_ref.collection("history").add({
                    "version": 1,
                    "value": validated,
                    "previous_value": None,
                    "changed_by": current_user["uid"],
                    "changed_at": now,
                    "reason": f"{source_type} sync (initial)",
                })

            synced += 1
        except Exception as e:
            logger.exception("Failed to sync field '%s'", source_field)
            errors.append(f"Field '{source_field}': {e}")

    return {"success": len(errors) == 0, "synced_count": synced, "error_count": len(errors), "errors": errors}

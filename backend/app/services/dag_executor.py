"""DAG execution service — manages spreadsheet calculation graph."""
import logging
from datetime import UTC, datetime
from typing import Any

from backend.app.config import get_firestore_client, settings
from backend.app.services.excel_engine import calculate_model

logger = logging.getLogger(__name__)


def _get_project_ref(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id)


def get_model_file(project_id: str) -> bytes | None:
    """Get the stored .xlsx model file for a project."""
    doc = _get_project_ref(project_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    # Model file stored as base64 in Firestore (or could be in Drive)
    import base64
    model_b64 = data.get("model_file_b64")
    if model_b64:
        return base64.b64decode(model_b64)
    return None


def store_model_file(project_id: str, file_bytes: bytes) -> None:
    """Store the .xlsx model file for a project."""
    import base64
    _get_project_ref(project_id).update({
        "model_file_b64": base64.b64encode(file_bytes).decode(),
        "updated_at": datetime.now(UTC),
    })


def get_assumptions_as_cell_map(project_id: str) -> dict[str, Any]:
    """Collect all assumptions for a project and map them to Excel cell references.

    Returns the structure expected by calculate_model().
    """
    db = get_firestore_client()
    prefix = settings.firestore_collection_prefix
    assumptions_ref = db.collection(f"{prefix}projects").document(project_id).collection("assumptions")

    # Get input mappings from project config
    project_doc = _get_project_ref(project_id).get()
    project_data = project_doc.to_dict() if project_doc.exists else {}
    input_mappings = project_data.get("input_mappings", {})

    # Build cell map from assumptions + mappings
    cell_map: dict[str, Any] = {}
    for doc in assumptions_ref.where("format", "==", "key_value").stream():
        data = doc.to_dict()
        key = data.get("key", "")
        value = data.get("value")
        if key in input_mappings and value is not None:
            cell_ref = input_mappings[key]
            cell_map[cell_ref] = value

    return {"key_values": cell_map, "table_injections": []}


def run_calculation(project_id: str) -> dict[str, Any]:
    """Run the full calculation for a project.

    1. Get the model .xlsx file
    2. Collect assumptions and map to cells
    3. Run calculate_model()
    4. Cache outputs in Firestore
    """
    # Get model file
    model_bytes = get_model_file(project_id)
    if not model_bytes:
        return {"success": False, "errors": ["No model file uploaded for this project"]}

    # Mark as calculating
    now = datetime.now(UTC)
    _get_project_ref(project_id).update({"calculation_status": "calculating", "updated_at": now})

    try:
        # Get assumptions mapped to cells
        assumptions = get_assumptions_as_cell_map(project_id)

        # Calculate
        outputs = calculate_model(model_bytes, assumptions)

        # Cache outputs
        _get_project_ref(project_id).update({
            "calculation_status": "done",
            "cached_outputs": outputs,
            "last_calculated_at": now,
            "updated_at": now,
        })

        return {"success": True, "nodes_calculated": 1, "errors": [], "outputs": outputs}

    except Exception as e:
        logger.exception("Calculation failed for project %s", project_id)
        _get_project_ref(project_id).update({
            "calculation_status": "error",
            "calculation_error": str(e),
            "updated_at": datetime.now(UTC),
        })
        return {"success": False, "errors": [str(e)]}

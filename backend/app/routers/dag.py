"""DAG router — trigger calculation per scenario."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.dag import CalculationResult
from backend.app.services.dag_executor import run_calculation

router = APIRouter(prefix="/api/projects/{project_id}/calculate", tags=["dag"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.post("", response_model=CalculationResult)
async def trigger_calculation(
    project_id: str,
    current_user: CurrentUser,
    scenario_id: str | None = None,
):
    """Trigger calculation for a project, optionally with a specific scenario.

    If scenario_id is provided, uses that TGV's values.
    If not, uses the legacy per-project assumptions.
    """
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}projects").document(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")

    result = run_calculation(project_id, scenario_id=scenario_id)
    return CalculationResult(**result)


@router.post("/batch", response_model=list[CalculationResult])
async def batch_calculation(
    project_id: str,
    scenario_ids: list[str],
    current_user: CurrentUser,
):
    """Calculate multiple scenarios for comparison / sensitivity analysis.

    Returns one result per scenario.
    """
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}projects").document(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")

    results = []
    for sid in scenario_ids:
        result = run_calculation(project_id, scenario_id=sid)
        results.append(CalculationResult(**result))
    return results

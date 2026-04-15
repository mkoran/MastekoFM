"""DAG router — trigger calculation, get outputs."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.models.dag import CalculationResult
from backend.app.services.dag_executor import run_calculation

router = APIRouter(prefix="/api/projects/{project_id}/calculate", tags=["dag"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.post("", response_model=CalculationResult)
async def trigger_calculation(project_id: str, current_user: CurrentUser):
    """Trigger a full recalculation of the project model.

    Injects current assumptions into the Excel model, recalculates with
    LibreOffice, and caches the outputs.
    """
    # Verify project exists
    prefix = settings.firestore_collection_prefix
    doc = get_firestore_client().collection(f"{prefix}projects").document(project_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")

    result = run_calculation(project_id)
    return CalculationResult(**result)

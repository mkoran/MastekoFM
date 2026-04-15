"""DAG router."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/dag", tags=["dag"])

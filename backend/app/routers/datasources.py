"""Data sources router."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/datasources", tags=["datasources"])

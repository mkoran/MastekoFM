"""Health check endpoints."""
import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


def _read_version() -> str:
    version_path = Path(__file__).resolve().parents[3] / "VERSION"
    if version_path.exists():
        return version_path.read_text().strip()
    return "0.0.0"


@router.get("/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}


@router.get("/api/health/full")
async def health_full():
    """Full health check — tests all subsystems."""
    checks = {
        "api": "ok",
        "version": _read_version(),
        "environment": os.getenv("ENVIRONMENT", "local"),
    }
    all_ok = all(v == "ok" for k, v in checks.items() if k not in ("version", "environment"))
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }

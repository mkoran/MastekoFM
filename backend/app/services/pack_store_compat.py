"""Compat shim for Sprint A — load bytes for any of (Model, AssumptionPack, OutputTemplate)
regardless of where they live (GCS or Drive).

In Sprint B these entities will be renamed and the duplication here will collapse.
For now we keep the loaders in one place so the runs router stays clean.
"""
from __future__ import annotations

from typing import Any

from backend.app.services import drive_service, storage_service


def load_model_bytes(model: dict[str, Any]) -> bytes:
    """Models in Sprint A are still stored as ExcelTemplate (GCS or Drive)."""
    if model.get("drive_file_id"):
        content = drive_service.download_file(model["drive_file_id"])
        if content is None:
            raise RuntimeError(f"Drive download failed for model file_id={model['drive_file_id']}")
        return content
    if model.get("storage_path"):
        return storage_service.download_xlsx(model["storage_path"])
    raise ValueError("Model has neither drive_file_id nor storage_path")


def load_pack_bytes(pack: dict[str, Any], *, user_token: str | None = None) -> bytes:
    """AssumptionPacks (Scenarios) are GCS or Drive."""
    if pack.get("storage_kind") == "drive_xlsx" or pack.get("drive_file_id"):
        if not pack.get("drive_file_id"):
            raise ValueError("Drive-backed pack has no drive_file_id")
        content = drive_service.download_file(pack["drive_file_id"], user_access_token=user_token)
        if content is None:
            raise RuntimeError(f"Drive download failed for pack file_id={pack['drive_file_id']}")
        return content
    if pack.get("storage_path"):
        return storage_service.download_xlsx(pack["storage_path"])
    raise ValueError("AssumptionPack has neither drive_file_id nor storage_path")


def load_output_template_bytes(tpl: dict[str, Any], *, user_token: str | None = None) -> bytes:
    """OutputTemplates are Drive-only (Sprint A design)."""
    if not tpl.get("drive_file_id"):
        raise ValueError("OutputTemplate must be Drive-backed")
    content = drive_service.download_file(tpl["drive_file_id"], user_access_token=user_token)
    if content is None:
        raise RuntimeError(f"Drive download failed for output_template file_id={tpl['drive_file_id']}")
    return content

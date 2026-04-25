"""Tree Navigator endpoints (Sprint A.5).

Provides the data the left-tree expand operations and right-pane detail views need:
  - Inputs flat list per AssumptionPack
  - Outputs flat list per AssumptionPack (from latest successful Run)
  - Single-cell detail for an Input or Output
  - Time-series of an Output cell across all Runs
"""
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.config import get_firestore_client, settings
from backend.app.middleware.auth import get_current_user
from backend.app.services import pack_store, storage_service, tree_browser

router = APIRouter(tags=["tree"])

CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _project_doc(project_id: str):
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}projects").document(project_id)


def _pack_doc(project_id: str, pack_id: str):
    return _project_doc(project_id).collection("assumption_packs").document(pack_id)


def _runs_ref():
    prefix = settings.firestore_collection_prefix
    return get_firestore_client().collection(f"{prefix}runs")


def _load_pack_or_404(project_id: str, pack_id: str) -> dict[str, Any]:
    doc = _pack_doc(project_id, pack_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="AssumptionPack not found")
    return doc.to_dict()


@router.get("/api/projects/{project_id}/assumption-packs/{pack_id}/inputs")
async def list_pack_inputs(project_id: str, pack_id: str, current_user: CurrentUser):
    """Read the AssumptionPack's I_ tab cells. Returns a flat list."""
    pack = _load_pack_or_404(project_id, pack_id)
    try:
        xlsx_bytes = pack_store.load_pack_bytes_compat(pack)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load pack file: {exc}") from exc
    cells = tree_browser.list_input_cells(xlsx_bytes)
    return {"pack_id": pack_id, "tab_count": len(set(c["tab"] for c in cells)), "cells": cells}


@router.get("/api/projects/{project_id}/assumption-packs/{pack_id}/outputs")
async def list_pack_outputs(project_id: str, pack_id: str, current_user: CurrentUser):
    """Read the latest successful Run's output O_ cells for this AssumptionPack.

    If there are no successful Runs, returns an empty list with a hint.
    """
    _load_pack_or_404(project_id, pack_id)

    # Find the most recent completed Run for this pack
    q = (
        _runs_ref()
        .where("assumption_pack_id", "==", pack_id)
        .where("status", "==", "completed")
        .order_by("started_at", direction="DESCENDING")
        .limit(1)
    )
    docs = list(q.stream())
    if not docs:
        return {
            "pack_id": pack_id,
            "run_id": None,
            "cells": [],
            "hint": "No successful runs yet — pick a Model + OutputTemplate and click Run.",
        }
    run_doc = docs[0]
    run = run_doc.to_dict()
    out_path = run.get("output_storage_path")
    if not out_path:
        return {"pack_id": pack_id, "run_id": run_doc.id, "cells": [], "hint": "Run has no output path"}

    try:
        out_bytes = storage_service.download_xlsx(out_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load output file: {exc}") from exc
    cells = tree_browser.list_output_cells(out_bytes)

    return {
        "pack_id": pack_id,
        "run_id": run_doc.id,
        "run_started_at": run.get("started_at"),
        "model_id": run.get("model_id"),
        "model_version": run.get("model_version"),
        "output_template_id": run.get("output_template_id"),
        "output_template_version": run.get("output_template_version"),
        "tab_count": len(set(c["tab"] for c in cells)),
        "cells": cells,
    }


@router.get("/api/projects/{project_id}/assumption-packs/{pack_id}/inputs/{tab}/{cell_ref}")
async def get_input_cell(
    project_id: str, pack_id: str, tab: str, cell_ref: str, current_user: CurrentUser
):
    """Single-cell focus view for an input cell."""
    pack = _load_pack_or_404(project_id, pack_id)
    xlsx_bytes = pack_store.load_pack_bytes_compat(pack)
    cells = tree_browser.list_input_cells(xlsx_bytes)
    match = next((c for c in cells if c["tab"] == tab and c["cell_ref"] == cell_ref), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Cell {tab}!{cell_ref} not found")
    return {
        "pack_id": pack_id,
        "tab": tab,
        "cell_ref": cell_ref,
        **match,
        "pack_name": pack.get("name"),
        "pack_version": pack.get("version", 1),
        "drive_file_id": pack.get("drive_file_id"),
        "edit_url": (
            f"https://docs.google.com/spreadsheets/d/{pack['drive_file_id']}/edit"
            if pack.get("drive_file_id")
            else None
        ),
    }


@router.get("/api/projects/{project_id}/assumption-packs/{pack_id}/outputs/{tab}/{cell_ref}/history")
async def get_output_cell_history(
    project_id: str, pack_id: str, tab: str, cell_ref: str, current_user: CurrentUser
):
    """Time-series of an output cell value across all successful Runs of this pack."""
    _load_pack_or_404(project_id, pack_id)

    q = (
        _runs_ref()
        .where("assumption_pack_id", "==", pack_id)
        .where("status", "==", "completed")
        .order_by("started_at", direction="ASCENDING")
    )
    history: list[dict[str, Any]] = []
    for run_doc in q.stream():
        run = run_doc.to_dict()
        out_path = run.get("output_storage_path")
        if not out_path:
            continue
        try:
            out_bytes = storage_service.download_xlsx(out_path)
            cells = tree_browser.list_output_cells(out_bytes)
        except Exception:
            continue
        match = next((c for c in cells if c["tab"] == tab and c["cell_ref"] == cell_ref), None)
        if not match:
            continue
        history.append(
            {
                "run_id": run_doc.id,
                "started_at": run.get("started_at", datetime.now(UTC)),
                "value": match["value"],
                "model_id": run.get("model_id"),
                "model_version": run.get("model_version"),
                "output_template_id": run.get("output_template_id"),
                "output_template_version": run.get("output_template_version"),
            }
        )
    return {"pack_id": pack_id, "tab": tab, "cell_ref": cell_ref, "history": history}

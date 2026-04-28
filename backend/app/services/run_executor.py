"""Two-stage Run executor — the heart of three-way composition.

Stage 1 (Model):
    overlay AssumptionPack.I_* onto Model.I_*
    LibreOffice recalc
    extract Model.O_* tab values

Stage 2 (OutputTemplate):
    inject extracted O_<name> values into OutputTemplate.M_<name> cells
    LibreOffice recalc
    save → final artifact bytes

For format != "xlsx" (PDF/Word/GoogleDoc), Stage 2 dispatches to a renderer
module instead. Sprint D adds PDF; Sprint H adds Word + Google Doc.

This module is sync (Sprint A). Sprint C wraps it in a Cloud Tasks worker.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.app.services import excel_engine, excel_template_engine

logger = logging.getLogger(__name__)


def execute_run_sync(
    *,
    model_bytes: bytes,
    pack_bytes: bytes,
    output_template_bytes: bytes,
    output_template_format: str = "xlsx",
) -> dict[str, Any]:
    """Run the full two-stage pipeline.

    Returns:
      {
        "output_bytes": bytes,
        "warnings": list[str],
        "stage1_recalculated": bool,
        "stage2_recalculated": bool,
        "model_outputs": dict[str, dict[str, Any]],   # for debugging / surfacing in UI
      }

    Raises ValueError on contract violations (validator should have caught these,
    but this is the defense-in-depth layer at execution time).
    """
    if output_template_format != "xlsx":
        raise NotImplementedError(
            f"OutputTemplate format {output_template_format!r} not yet supported "
            "(Sprint D adds pdf, Sprint H adds docx + google_doc)"
        )

    # ── Stage 1 — Model ────────────────────────────────────────────────────
    logger.info("Stage 1: overlay AssumptionPack onto Model + recalc")
    merged_model_bytes, warnings_stage1 = excel_template_engine.overlay_scenario_on_template(
        model_bytes, pack_bytes
    )
    recalced_model_bytes = excel_engine.recalculate_with_libreoffice(merged_model_bytes)
    if recalced_model_bytes is None:
        # LibreOffice not available (local tests without LO); fall back to merged but warn.
        warnings_stage1.append("LibreOffice not available; Stage 1 not recalculated")
        recalced_model_bytes = merged_model_bytes
        stage1_recalculated = False
    else:
        stage1_recalculated = True

    model_outputs = excel_template_engine.extract_model_outputs(recalced_model_bytes)
    logger.info(
        "Stage 1 done: %d O_ tab(s) extracted (%s)",
        len(model_outputs),
        ", ".join(model_outputs.keys()),
    )

    # ── Stage 2 — OutputTemplate ───────────────────────────────────────────
    logger.info("Stage 2: inject Model outputs into OutputTemplate + recalc")
    merged_template_bytes, warnings_stage2 = excel_template_engine.overlay_outputs_onto_template(
        output_template_bytes, model_outputs
    )
    recalced_template_bytes = excel_engine.recalculate_with_libreoffice(merged_template_bytes)
    if recalced_template_bytes is None:
        warnings_stage2.append("LibreOffice not available; Stage 2 not recalculated")
        recalced_template_bytes = merged_template_bytes
        stage2_recalculated = False
    else:
        stage2_recalculated = True

    return {
        "output_bytes": recalced_template_bytes,
        "warnings": warnings_stage1 + warnings_stage2,
        "stage1_recalculated": stage1_recalculated,
        "stage2_recalculated": stage2_recalculated,
        "model_outputs": model_outputs,
    }

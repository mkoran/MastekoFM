"""Excel Template engine — tab classification, Scenario extraction, overlay, validate.

The architecture in one line:
  Template = .xlsx with tabs prefixed I_ / O_ / other (calc)
  Scenario = .xlsx containing only the Template's I_ tabs (edited by humans)
  Calculate = cell-copy Scenario's I_ tabs over Template's I_ tabs, recalc.

Prefix matching is CASE-SENSITIVE. "I_Rev" is an input; "i_Rev" is a calc tab.

Spike proven on Campus_Adele_Model_20260416_1410.xlsx — see /tmp/mfm_spike_*.py.
"""
from __future__ import annotations

import io
import logging
from copy import copy
from typing import Any

import openpyxl
from openpyxl.cell.cell import MergedCell

logger = logging.getLogger(__name__)

INPUT_PREFIX = "I_"
OUTPUT_PREFIX = "O_"


def classify_tabs(wb: openpyxl.Workbook) -> dict[str, list[str]]:
    """Classify a workbook's tabs by case-sensitive prefix.

    Returns {"input_tabs": [...], "output_tabs": [...], "calc_tabs": [...]}.
    Ordering follows the sheet order in the workbook.
    """
    input_tabs: list[str] = []
    output_tabs: list[str] = []
    calc_tabs: list[str] = []
    for name in wb.sheetnames:
        if name.startswith(INPUT_PREFIX):
            input_tabs.append(name)
        elif name.startswith(OUTPUT_PREFIX):
            output_tabs.append(name)
        else:
            calc_tabs.append(name)
    return {"input_tabs": input_tabs, "output_tabs": output_tabs, "calc_tabs": calc_tabs}


def classify_bytes(content: bytes) -> dict[str, list[str]]:
    """Convenience: classify tabs directly from file bytes."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    try:
        return classify_tabs(wb)
    finally:
        wb.close()


def validate_template(wb: openpyxl.Workbook) -> list[str]:
    """Return a list of human-readable validation errors. Empty list = valid.

    Rules:
      - At least one I_ tab must exist.
      - No duplicate tab names (openpyxl enforces this but we surface a clearer error).
      - Tab names must not begin with an ASCII dot (Excel rejects these).
    """
    errors: list[str] = []
    classes = classify_tabs(wb)
    if not classes["input_tabs"]:
        errors.append("Template has no I_ tabs. At least one input tab is required.")
    if len(wb.sheetnames) != len(set(wb.sheetnames)):
        errors.append("Template has duplicate tab names.")
    for n in wb.sheetnames:
        if n.startswith("."):
            errors.append(f"Tab name {n!r} is invalid (starts with a dot).")
    return errors


def extract_scenario_from_template(template_bytes: bytes) -> bytes:
    """Produce an inputs-only .xlsx from a Template — the initial Scenario file.

    Deletes every tab that isn't I_*. The resulting file is what the user edits
    in Drive / Excel. Note: some cells in I_ tabs may reference calc tabs and
    will display #REF! when opened standalone; they resolve correctly once
    overlaid back into the Template for calculation.
    """
    wb = openpyxl.load_workbook(io.BytesIO(template_bytes), data_only=False)
    try:
        to_delete = [n for n in wb.sheetnames if not n.startswith(INPUT_PREFIX)]
        for n in to_delete:
            del wb[n]
        if not wb.sheetnames:
            # openpyxl requires at least one sheet; add a placeholder if somehow empty
            wb.create_sheet("I_Empty")
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    finally:
        wb.close()


def _overlay_tab(src_ws, dst_ws) -> None:
    """Cell-by-cell copy of src_ws content into dst_ws, including styles and merges.

    Destination merged ranges are unmerged first (MergedCells are read-only),
    then destination cells within the source's used range are cleared, then
    source cells are copied, then source merges are re-applied.
    """
    # Step 1: unmerge destination
    for merge in list(dst_ws.merged_cells.ranges):
        dst_ws.unmerge_cells(str(merge))

    # Step 2: clear destination cells within the source's used range, to guard
    # against stale rows/columns left over from a previous (larger) version.
    max_row = src_ws.max_row or 1
    max_col = src_ws.max_column or 1
    for row in dst_ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
        for c in row:
            c.value = None

    # Step 3: copy source cells (value + style)
    for row in src_ws.iter_rows():
        for sc in row:
            if isinstance(sc, MergedCell):
                continue
            dc = dst_ws.cell(row=sc.row, column=sc.column)
            dc.value = sc.value
            if sc.has_style:
                dc.font = copy(sc.font)
                dc.fill = copy(sc.fill)
                dc.border = copy(sc.border)
                dc.alignment = copy(sc.alignment)
                dc.number_format = sc.number_format
                dc.protection = copy(sc.protection)

    # Step 4: column widths and row heights
    for col_letter, dim in src_ws.column_dimensions.items():
        if dim.width:
            dst_ws.column_dimensions[col_letter].width = dim.width
    for r, dim in src_ws.row_dimensions.items():
        if dim.height:
            dst_ws.row_dimensions[r].height = dim.height

    # Step 5: re-apply source merges
    for merge in src_ws.merged_cells.ranges:
        dst_ws.merge_cells(str(merge))


def overlay_scenario_on_template(
    template_bytes: bytes, scenario_bytes: bytes
) -> tuple[bytes, list[str]]:
    """Merge a Scenario's I_ tabs into a copy of the Template workbook.

    Returns (merged_file_bytes, warnings).
    Raises ValueError on hard contract violations.
    """
    tpl = openpyxl.load_workbook(io.BytesIO(template_bytes), data_only=False)
    sc = openpyxl.load_workbook(io.BytesIO(scenario_bytes), data_only=False)
    warnings: list[str] = []
    try:
        tpl_classes = classify_tabs(tpl)
        sc_classes = classify_tabs(sc)

        # Contract: Scenario must contain ONLY I_ tabs
        if sc_classes["output_tabs"] or sc_classes["calc_tabs"]:
            bad = sc_classes["output_tabs"] + sc_classes["calc_tabs"]
            raise ValueError(
                "Scenario file contains tabs that are not I_ tabs: "
                + ", ".join(bad)
            )

        # Contract: every I_ tab the Template declares must be in the Scenario
        tpl_inputs = set(tpl_classes["input_tabs"])
        sc_inputs = set(sc_classes["input_tabs"])
        missing = tpl_inputs - sc_inputs
        if missing:
            raise ValueError(
                "Scenario is missing required input tabs: " + ", ".join(sorted(missing))
            )

        # Warn if Scenario has extra I_ tabs the Template doesn't know about
        extra = sc_inputs - tpl_inputs
        if extra:
            warnings.append(
                "Scenario has extra I_ tabs not in Template (ignored): "
                + ", ".join(sorted(extra))
            )

        # Overlay each I_ tab
        for name in tpl_classes["input_tabs"]:
            _overlay_tab(sc[name], tpl[name])

        buf = io.BytesIO()
        tpl.save(buf)
        return buf.getvalue(), warnings
    finally:
        tpl.close()
        sc.close()


def replace_template_tabs(
    existing_template_bytes: bytes, new_template_bytes: bytes
) -> tuple[bytes, dict[str, Any]]:
    """Upgrade an existing Template with I_/O_ tabs from a new upload (Option A).

    Behavior per agreed design:
      - Calc tabs (non-prefixed): replaced wholesale from the new file.
      - I_ tabs: each I_ tab in the new file replaces the corresponding one in
        the existing template. New I_ tabs are added. I_ tabs only in the old
        template are removed.
      - O_ tabs: same as I_ tabs (derived, no user data).

    In practice this is identical to "the new upload becomes the Template",
    but named distinctly so routers can express intent. The function also
    reports a diff so the caller can surface a confirmation to the user.
    """
    # Classify both for the diff report
    old_classes = classify_bytes(existing_template_bytes)
    new_classes = classify_bytes(new_template_bytes)

    def diff(old: list[str], new: list[str]) -> dict[str, list[str]]:
        old_set, new_set = set(old), set(new)
        return {
            "added": sorted(new_set - old_set),
            "removed": sorted(old_set - new_set),
            "kept": sorted(old_set & new_set),
        }

    report = {
        "input_tabs": diff(old_classes["input_tabs"], new_classes["input_tabs"]),
        "output_tabs": diff(old_classes["output_tabs"], new_classes["output_tabs"]),
        "calc_tabs": diff(old_classes["calc_tabs"], new_classes["calc_tabs"]),
    }
    # Option A: the new file IS the new Template content.
    return new_template_bytes, report


def calculate(
    template_bytes: bytes, scenario_bytes: bytes
) -> dict[str, Any]:
    """Full Calculate pipeline: overlay + LibreOffice recalc.

    Returns {
      "output_bytes": bytes | None,
      "merged_bytes": bytes,        # pre-recalc, in case caller wants it
      "warnings": [...],
      "recalculated": bool,
    }
    """
    from backend.app.services import excel_engine

    merged_bytes, warnings = overlay_scenario_on_template(template_bytes, scenario_bytes)
    recalced = excel_engine.recalculate_with_libreoffice(merged_bytes)
    return {
        "output_bytes": recalced or merged_bytes,
        "merged_bytes": merged_bytes,
        "warnings": warnings,
        "recalculated": recalced is not None,
    }

"""Excel calculation engine — inject values, recalculate, extract results.

Flow: openpyxl injects → save temp .xlsx → LibreOffice recalculates → openpyxl reads results.
"""
import io
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any

import openpyxl

logger = logging.getLogger(__name__)

LIBREOFFICE_TIMEOUT = 30  # seconds


def _find_libreoffice() -> str | None:
    """Find LibreOffice binary."""
    for path in ["/usr/bin/libreoffice", "/usr/bin/soffice", shutil.which("libreoffice"), shutil.which("soffice")]:
        if path and os.path.isfile(path):
            return path
    return None


def inject_values(wb: openpyxl.Workbook, sheet_name: str, cell_map: dict[str, Any]) -> int:
    """Inject values into specific cells of a worksheet.

    cell_map: {"B5": "Campus Adele", "B7": "2025-03-01", "B8": 13, ...}
    Skips merged cells gracefully. Returns count of successfully injected values.
    """
    ws = wb[sheet_name]
    injected = 0
    for cell_ref, value in cell_map.items():
        try:
            cell = ws[cell_ref]
            if hasattr(cell, "value") and not isinstance(cell, openpyxl.cell.cell.MergedCell):
                cell.value = value
                injected += 1
            else:
                logger.warning("Skipping merged/read-only cell %s in %s", cell_ref, sheet_name)
        except (AttributeError, TypeError):
            logger.warning("Could not inject into cell %s in %s", cell_ref, sheet_name)
    return injected


def inject_table_data(wb: openpyxl.Workbook, sheet_name: str, start_row: int, columns: list[str], rows: list[dict[str, Any]]) -> None:
    """Inject table data into a worksheet starting at a specific row.

    columns: ["B", "C", "D", ...] — column letters
    rows: list of dicts with column values
    """
    ws = wb[sheet_name]
    for i, row_data in enumerate(rows):
        for col_letter, key in zip(columns, row_data.keys(), strict=False):
            cell_ref = f"{col_letter}{start_row + i}"
            ws[cell_ref] = row_data[key]


def recalculate_with_libreoffice(file_bytes: bytes) -> bytes | None:
    """Recalculate an .xlsx file using LibreOffice headless.

    Returns the recalculated file bytes, or None if LibreOffice is not available.
    """
    lo_path = _find_libreoffice()
    if not lo_path:
        logger.warning("LibreOffice not found — skipping recalculation")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "model.xlsx")
        with open(input_path, "wb") as f:
            f.write(file_bytes)

        try:
            result = subprocess.run(
                [lo_path, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", tmpdir, input_path],
                capture_output=True,
                timeout=LIBREOFFICE_TIMEOUT,
                cwd=tmpdir,
            )
            if result.returncode != 0:
                logger.error("LibreOffice failed: %s", result.stderr.decode())
                return None

            output_path = os.path.join(tmpdir, "model.xlsx")
            with open(output_path, "rb") as f:
                return f.read()

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice timed out after %ds", LIBREOFFICE_TIMEOUT)
            return None
        except Exception:
            logger.exception("LibreOffice recalculation failed")
            return None


def extract_cell_values(wb: openpyxl.Workbook, extractions: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    """Extract values from specific cells across sheets.

    extractions: {"Annual Summary": ["B9", "C9", "D9", ...], "Sources & Uses": ["B6", "B7"]}
    Returns: {"Annual Summary": {"B9": 121408, "C9": 1486034, ...}}
    """
    results: dict[str, dict[str, Any]] = {}
    for sheet_name, cells in extractions.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        sheet_results: dict[str, Any] = {}
        for cell_ref in cells:
            sheet_results[cell_ref] = ws[cell_ref].value
        results[sheet_name] = sheet_results
    return results


def extract_table(wb: openpyxl.Workbook, sheet_name: str, start_row: int, end_row: int, columns: dict[str, str]) -> list[dict[str, Any]]:
    """Extract a table range from a worksheet.

    columns: {"A": "label", "B": "year_1", "C": "year_2", ...}
    Returns list of row dicts.
    """
    if sheet_name not in wb.sheetnames:
        return []
    ws = wb[sheet_name]
    rows = []
    for row_idx in range(start_row, end_row + 1):
        row_data: dict[str, Any] = {}
        has_data = False
        for col_letter, key in columns.items():
            val = ws[f"{col_letter}{row_idx}"].value
            row_data[key] = val
            if val is not None:
                has_data = True
        if has_data:
            rows.append(row_data)
    return rows


def calculate_model(model_bytes: bytes, assumptions: dict[str, Any]) -> dict[str, Any]:
    """Full calculation pipeline for a financial model.

    1. Load the .xlsx template
    2. Inject assumption values into input cells
    3. Recalculate with LibreOffice (or return raw if unavailable)
    4. Extract output values

    Returns dict with all calculated outputs.
    """
    # Step 1: Try injection + LibreOffice recalculation
    recalced_bytes = None
    try:
        wb = openpyxl.load_workbook(io.BytesIO(model_bytes))
        kv_map = assumptions.get("key_values", {})
        if kv_map and "Inputs & Assumptions" in wb.sheetnames:
            count = inject_values(wb, "Inputs & Assumptions", kv_map)
            logger.info("Injected %d/%d values", count, len(kv_map))
        for table_inject in assumptions.get("table_injections", []):
            inject_table_data(wb, table_inject["sheet"], table_inject["start_row"],
                              table_inject["columns"], table_inject["rows"])
        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        recalced_bytes = recalculate_with_libreoffice(buf.getvalue())
    except Exception:
        logger.exception("Injection/recalc failed")

    # Step 2: Read results — prefer recalculated, fall back to original cached values
    source = recalced_bytes if recalced_bytes else model_bytes
    result_wb = openpyxl.load_workbook(io.BytesIO(source), data_only=True)

    # Extract outputs
    outputs: dict[str, Any] = {}

    # Sources & Uses
    outputs["sources_and_uses"] = extract_table(
        result_wb, "Sources & Uses - Construction", 4, 30,
        {"A": "item", "B": "amount", "C": "notes"}
    )

    # Annual Summary
    outputs["annual_summary"] = extract_table(
        result_wb, "Annual Summary", 3, 130,
        {"A": "item", "B": "year_1", "C": "year_2", "D": "year_3", "E": "year_4", "F": "year_5", "G": "year_6", "H": "total", "I": "disposition"}
    )

    # Construction Budget Summary
    outputs["budget_summary"] = extract_table(
        result_wb, "Construction Budget & Draws", 4, 17,
        {"A": "category", "B": "amount"}
    )

    # Senior Construction Financing params
    if "Senior Construction Financing" in result_wb.sheetnames:
        sf = result_wb["Senior Construction Financing"]
        outputs["construction_loan"] = {
            "ltc": sf["B5"].value,
            "interest_rate": sf["B6"].value,
            "commitment_fee": sf["B7"].value,
            "total_project_cost": sf["B8"].value,
            "max_loan_amount": sf["B9"].value,
        }

    # Permanent Financing params
    if "Permanent Financing" in result_wb.sheetnames:
        pf = result_wb["Permanent Financing"]
        outputs["permanent_loan"] = {
            "loan_amount": pf["B4"].value,
            "interest_rate": pf["B5"].value,
            "amortization_years": pf["B7"].value,
            "loan_term_months": pf["B9"].value,
            "monthly_payment": pf["B10"].value,
        }

    result_wb.close()
    return outputs

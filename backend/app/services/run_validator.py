"""Three-way composition compatibility validator.

Given (Model, AssumptionPack, OutputTemplate) — usually as Firestore dicts —
return a list of human-readable error strings. Empty list = compatible.

Used at three points:
  1. UI dropdowns: filter to only-compatible options as the user picks
  2. POST /api/runs/validate: preview check before submit
  3. POST /api/runs: defensive re-check at execution time
"""
from __future__ import annotations

from typing import Any


def validate_run_composition(
    model: dict[str, Any],
    pack: dict[str, Any],
    output_template: dict[str, Any],
) -> list[str]:
    """Return [] if compatible, else a list of error strings.

    All three params are Firestore-shaped dicts with at minimum:
      model:           {input_tabs: [str], output_tabs: [str], m_tabs: [str], ...}
      pack:            {input_tabs: [str], output_tabs: [str], m_tabs: [str], calc_tabs: [str], ...}
      output_template: {m_tabs: [str], output_tabs: [str], ...}

    Rules:
      1. AssumptionPack provides every Model input tab (by name match)
      2. AssumptionPack contains ONLY I_ tabs (no O_, M_, calc)
      3. Every M_<name> in OutputTemplate has a matching O_<name> in Model
    """
    errors: list[str] = []

    model_inputs = set(model.get("input_tabs", []))
    pack_inputs = set(pack.get("input_tabs", []))
    pack_outputs = set(pack.get("output_tabs", []))
    pack_m = set(pack.get("m_tabs", []))
    pack_calc = set(pack.get("calc_tabs", []))
    model_outputs = set(model.get("output_tabs", []))
    template_m = set(output_template.get("m_tabs", []))

    # Rule 1
    missing_inputs = model_inputs - pack_inputs
    if missing_inputs:
        errors.append(
            "AssumptionPack missing required input tabs: " + ", ".join(sorted(missing_inputs))
        )

    # Rule 2
    pack_extra = pack_outputs | pack_m | pack_calc
    if pack_extra:
        errors.append(
            "AssumptionPack must contain only I_ tabs. Unexpected: "
            + ", ".join(sorted(pack_extra))
        )

    # Rule 3
    model_output_basenames = {t.removeprefix("O_") for t in model_outputs}
    template_m_basenames = {t.removeprefix("M_") for t in template_m}
    missing_outputs = template_m_basenames - model_output_basenames
    if missing_outputs:
        errors.append(
            "OutputTemplate requires Model outputs not present: "
            + ", ".join(f"O_{b}" for b in sorted(missing_outputs))
        )

    return errors

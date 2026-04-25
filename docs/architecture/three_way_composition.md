# Three-way composition

> The central architectural pattern of MastekoFM.

---

## Mental model

A financial model is made of three orthogonal things:

1. **The numbers a user wants to model** (e.g., "Construction Duration = 13 months, Land Cost = $400,000")
2. **The calculation logic** (e.g., "If Construction Duration > 12, then phase 2 financing kicks in...")
3. **The shape of the output** (e.g., "Investor Summary one-pager with IRR, NPV, equity multiple")

These change at different rates and are owned by different people:
- **Numbers** change every scenario (analyst varying assumptions)
- **Logic** changes occasionally (modeler refining the model)
- **Output shape** changes per audience (investor vs lender vs internal)

Tying any two of these together (e.g., "Project owns one Model and one Output template") couples things that have no business being coupled. Hence: three-way composition.

---

## The entities

```
AssumptionPack            Model                  OutputTemplate
─────────────             ─────                  ──────────────
  the numbers          the calc logic         the report layout
   (.xlsx)               (.xlsx)             (.xlsx / .pdf / .docx)
       \                    |                       /
        \                   |                      /
         \                  ▼                     /
          ────────▶  Run (composition) ◀─────────
                          │
                          ▼
                       Output
                  (artifact in Drive + GCS)
```

Each entity is independently versioned. A Run captures one specific version of each plus the resulting output.

---

## Why this matters

### Reusability

- One AssumptionPack ("Q1 2026 Base Case") can run against multiple Model versions (refactors, what-if structural changes) and multiple OutputTemplates (investor summary AND lender package AND internal review).
- One Model can be used by hundreds of AssumptionPacks across hundreds of Projects.
- One OutputTemplate is reusable across any compatible Model.

### Reproducibility

A Run record stores `(model_id, model_version, model_drive_revision_id, pack_id, pack_version, pack_drive_revision_id, output_template_id, output_template_version, output_template_drive_revision_id)`. To reproduce, fetch all three at the recorded revisions and re-execute.

### Independent evolution

A modeler refactoring the calc logic doesn't break existing AssumptionPacks (their `I_*` tabs still match). A report designer revising the OutputTemplate doesn't break the Model (the `M_*` requirements still match). The compat validator catches mismatches before launch.

---

## Concrete example: Hello World

### `helloworld_model.xlsx` (Model)

```
Tab: I_Numbers       Tab: Calc                       Tab: O_Results
+---+----+           +---+--------------------+      +---+-------+
| a |  2 |           | A1 = =I_Numbers!B1+B2 |      | A1| sum   |
| b |  3 |           | A2 = =I_Numbers!B1*B2 |      | B1| =Calc!A1
+---+----+           +---+--------------------+      | A2| product|
                                                     | B2| =Calc!A2
                                                     +---+-------+
```

### `helloworld_inputs.xlsx` (AssumptionPack — only I_ tabs)

```
Tab: I_Numbers
+---+----+
| a |  5 |
| b |  7 |
+---+----+
```

### `helloworld_report.xlsx` (OutputTemplate — M_/calc/O_)

```
Tab: M_Results        Tab: O_Report
+---+-------+         +-----------------+
| A1| sum   |         | A1: Hello World Report
| B1| 0     | ←       | A3: Sum:    B3: =M_Results!B1
| A2| product         | A4: Product:B4: =M_Results!B2
| B2| 0     | ←       | A5: Total:  B5: =M_Results!B1+M_Results!B2
+---+-------+         +-----------------+
```

### Run pipeline

```
Stage 1 — Model:
  open helloworld_model.xlsx
  overlay helloworld_inputs.I_Numbers (a=5, b=7) onto helloworld_model.I_Numbers
  LibreOffice recalc
  → Model.O_Results: sum=12, product=35

Stage 2 — OutputTemplate:
  open helloworld_report.xlsx
  inject {sum: 12, product: 35} into helloworld_report.M_Results.B1, B2
  LibreOffice recalc
  → helloworld_report.O_Report: "Sum: 12   Product: 35   Total: 47"
  
Save the recalculated helloworld_report.xlsx as the output artifact.
```

If those numbers come out right, the entire 3-way pipeline is validated end-to-end.

---

## Compatibility rules

A Run is launchable iff:

```python
def validate_run(model: Model, pack: AssumptionPack, output_template: OutputTemplate) -> list[str]:
    errors = []
    
    # Rule 1: AssumptionPack must provide every Model input
    missing = set(model.input_tabs) - set(pack.input_tabs)
    if missing:
        errors.append(f"AssumptionPack missing required input tabs: {sorted(missing)}")
    
    # Rule 2: AssumptionPack contains ONLY I_* tabs
    if pack.has_non_input_tabs:
        errors.append("AssumptionPack must contain only I_ tabs")
    
    # Rule 3: Every M_<name> in OutputTemplate matches an O_<name> in Model
    model_outputs = {t.removeprefix("O_") for t in model.output_tabs}
    template_inputs = {t.removeprefix("M_") for t in output_template.m_tabs}
    missing_outputs = template_inputs - model_outputs
    if missing_outputs:
        errors.append(f"OutputTemplate requires Model outputs not present: {sorted(missing_outputs)}")
    
    return errors  # empty list = compatible
```

UI behavior:
- New Run modal shows three dropdowns
- Once one is picked (say Model), the other two filter to compatible options
- Submit button disabled if any errors
- Errors shown inline in the modal

---

## What's NOT in three-way composition

These are intentionally excluded from the composition entities:

- **Project** — a Project is just an organizational scope (members, Drive folder, defaults). It owns AssumptionPacks but doesn't constrain Model or OutputTemplate choice.
- **User identity** — captured on Run as `triggered_by`, not as part of the composition tuple.
- **Time** — Runs are timestamped but the composition is timeless. Versions are how you express temporal intent.
- **Workspace** — single workspace for now (multi-workspace is Phase 3).

---

## Future composition extensions (not yet implemented)

- **Model chains**: Output of one Model becomes Input of another Model in a single Run (true DAG). Out of scope for now — Excel cross-sheet refs cover most real cases.
- **Output template chains**: One OutputTemplate produces an .xlsx; another OutputTemplate consumes that and produces a PDF. Out of scope; can be expressed as two separate Runs.
- **Conditional composition**: "If IRR > 12%, run OutputTemplate A, else B." Out of scope; handled at the user level.

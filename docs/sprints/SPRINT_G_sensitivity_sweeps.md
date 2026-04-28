# Sprint G — Sensitivity sweeps + comparison UI

> Estimated: ~4-5 days
> Branch: `epic/sprint-g-sweeps`
> Goal: vary inputs systematically, run N variants, visualize impact.
> Blocked-by: Sprint C (async runs)

---

## Why

The whole reason to build a "modeling operating system" rather than a spreadsheet is to make sensitivity analysis fast. A user picks a base scenario, declares "vary this assumption from X to Y in N steps", and the system materializes N runs and shows a tornado chart of impact on key outputs.

---

## Definition of Done

- User can launch a Sweep from a base AssumptionPack
- Sweep declares: variable (cell or schema key), variation type (delta %, delta abs, list of values), N steps
- Backend materializes N AssumptionPacks (programmatic openpyxl mutation OR JSON variants)
- N Runs queued via Cloud Tasks
- Sweep status shows N/N completed
- Tornado chart displays for one-variable sweep
- Heatmap displays for two-variable sweep (optional)
- Run comparison view: side-by-side cell diff between any 2-N runs

---

## Stories

### G-001 · Sweep Firestore model (S)

```python
class Sweep:
    id: str
    project_id: str
    name: str
    base_pack_id: str
    base_pack_version: int
    base_model_id: str
    base_output_template_id: str
    variations: list[Variation]
    output_keys_to_compare: list[str]  # e.g., ["O_Annual Summary.B12"]
    status: Literal["pending", "running", "completed", "partial_failure"]
    materialized_pack_ids: list[str]
    run_ids: list[str]
    created_at, completed_at, triggered_by

class Variation:
    label: str                            # "+5%", "Conservative"
    target: VariationTarget
    delta_type: Literal["pct_relative", "abs_delta", "absolute"]
    delta: float | int | str

class VariationTarget:
    # Either cell-based or schema-key-based
    tab: str | None
    cell_ref: str | None
    schema_key: str | None
```

### G-002 · Sweep materializer (M)

`services/sweep_materializer.py`:
```python
def materialize_sweep(sweep: Sweep) -> list[str]:
    """For each Variation, create a derived AssumptionPack. Returns the pack IDs."""
    base_pack = load_pack(sweep.base_pack_id)
    base_bytes = drive.download(base_pack.drive_file_id)
    
    pack_ids = []
    for var in sweep.variations:
        # Compute the new value
        # Mutate the .xlsx (openpyxl) OR mutate the JSON (dict copy)
        # Save as a new AssumptionPack with a derived name (e.g., "BaseCase + 5% rent")
        # Tag with sweep_id for traceability
        pack_ids.append(new_pack_id)
    return pack_ids
```

### G-003 · POST /api/sweeps (S)

Validate, create Sweep doc, materialize N packs, enqueue N Runs (each as a Cloud Task using the Sprint C infrastructure). Return 202 with sweep_id.

### G-004 · Sweep results endpoint (S)

`GET /api/sweeps/{id}/results`:
```json
{
  "sweep_id": "...",
  "status": "completed",
  "runs": [
    {"variation_label": "-10%", "run_id": "...", "outputs": {"O_Annual Summary.B12": 1234567}},
    {"variation_label": "Base", "run_id": "...", "outputs": {"O_Annual Summary.B12": 1500000}},
    ...
  ]
}
```

### G-005 · Sweep builder UI (M)

`frontend/src/pages/SweepBuilderPage.tsx`:
- Pick base AssumptionPack
- Pick variable (dropdown of cells in I_ tabs OR schema keys)
- Pick variation type (delta %, delta abs, custom list)
- Enter range or values
- Pick output keys to compare
- "Launch Sweep" button

### G-006 · Tornado chart (S)

`frontend/src/components/TornadoChart.tsx` using Recharts. One-variable sweep → bar chart of output_value at each variation. Anchored at base value.

### G-007 · Heatmap (M)

For two-variable sweeps: NxM grid of output values. Color-coded. Hover for exact value.

### G-008 · Run comparison view (M)

`frontend/src/pages/RunComparePage.tsx`:
- Pick 2-N runs from a Sweep or freely
- Side-by-side table: shared output keys with values per run
- Highlight differences (heat-coloring by % change)
- Export to .xlsx

### G-009 · Tests: materialization (S)

Hello World Sweep: vary `a` from 1 to 10. Assert 10 packs created with correct values. Run all 10, assert outputs follow `sum=a+7`.

---

## Risks

| Risk | Mitigation |
|---|---|
| 100+ runs queued at once overwhelm Cloud Tasks | Set per-queue rate limit; surface in UI when queueing throttles |
| Materialized packs clutter Drive | Tag with sweep_id; auto-cleanup after sweep completes (configurable) |
| Comparison view performance with many cells | Virtualized table; collapse-by-O_-tab |
| User varies a non-numeric cell | Validator rejects at sweep launch |

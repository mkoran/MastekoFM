# Sprint A — Hello World vertical slice

> Estimated: ~5 days
> Branch: `epic/sprint-a-helloworld` (off `epic/excel-template-mvp`)
> Goal: working Hello World end-to-end so Marc can review the new UI before any deletes happen.
> Blocked-by: nothing
> Blocks: Sprint B (cleanup), Sprint D (PDF), Sprint E (multi-user)

---

## Why this sprint exists

Before deleting ~50% of the codebase, we want a working slice of the new architecture so Marc can:
1. See the three-way composition UI in action
2. Verify the engine produces correct numbers
3. Push back on UX before it's set in stone
4. Decide whether to proceed with deletes or iterate

This sprint builds the new world *alongside* the legacy code (legacy stays hidden behind `?legacy=1`). Sprint B does the actual deletes once direction is approved.

---

## Goal & Definition of Done

Marc can:
1. Open https://dev-masteko-fm.web.app
2. Sign in with Google
3. Navigate to a "Hello World" Project (auto-seeded by `/api/seed/helloworld`)
4. Click **+ New Run**
5. Modal opens with three dropdowns:
   - **Inputs**: Hello World Inputs
   - **Model**: Hello World Model
   - **Output**: Hello World Report
6. Hit **Run** → spinner → ~2s → output download link appears
7. Download the .xlsx → open in Excel → see `O_Report` showing:
   - Sum: 12
   - Product: 35
   - Total: 47

Plus:
- 102 existing tests still pass (no regressions)
- ~10 new tests added covering `M_*` prefix, run_validator, run_executor
- ruff clean, npm build clean
- Deployed to DEV at version 1.035 or higher

---

## Out of scope

| Item | Why deferred |
|---|---|
| Deleting legacy code | Sprint B — keep it parallel for now in case we iterate |
| Async runs (Cloud Tasks worker) | Sprint C — Hello World is <2s sync |
| PDF / Word / Google Doc renderers | Sprints D / H — `xlsx` only |
| Multi-user permissions | Sprint E — single-user for now |
| JSON AssumptionPacks | Sprint F — .xlsx only |
| Sensitivity sweeps | Sprint G |
| Re-seeding Campus Adele under new schema | Sprint B — keep current Campus Adele working as-is |
| Renaming entities in code (`ExcelTemplate→Model`) | Sprint B — wait until cleanup |

---

## Stories

### A-001 · Create Hello World seed files (XS)

**File**: `seed/helloworld/`

Three .xlsx files committed to the repo. Build them in Excel (or via openpyxl in a one-shot script):

#### `helloworld_model.xlsx`
- Tab `I_Numbers`:
  - A1=`a`, B1=`2` (literal placeholder)
  - A2=`b`, B2=`3`
- Tab `Calc`:
  - A1=`=I_Numbers!B1+I_Numbers!B2`
  - A2=`=I_Numbers!B1*I_Numbers!B2`
- Tab `O_Results`:
  - A1=`sum`, B1=`=Calc!A1`
  - A2=`product`, B2=`=Calc!A2`

#### `helloworld_inputs.xlsx`
- Tab `I_Numbers` only:
  - A1=`a`, B1=**5**
  - A2=`b`, B2=**7**

#### `helloworld_report.xlsx`
- Tab `M_Results`:
  - A1=`sum`, B1=`0` (placeholder — will be filled at run time)
  - A2=`product`, B2=`0`
- Tab `O_Report`:
  - A1=`Hello World Report`
  - A3=`Sum:`, B3=`=M_Results!B1`
  - A4=`Product:`, B4=`=M_Results!B2`
  - A5=`Total:`, B5=`=M_Results!B1+M_Results!B2`

Add `seed/helloworld/README.md` explaining the structure.

Also copy these into `tests/fixtures/` for engine tests.

---

### A-002 · Extend `excel_template_engine.classify_tabs()` for `M_*` (XS)

**File**: `backend/app/services/excel_template_engine.py`

Current `classify_tabs` returns `{input_tabs, output_tabs, calc_tabs}`. Add `m_tabs`:

```python
M_PREFIX = "M_"

def classify_tabs(wb: openpyxl.Workbook) -> dict[str, list[str]]:
    input_tabs, output_tabs, m_tabs, calc_tabs = [], [], [], []
    for name in wb.sheetnames:
        if name.startswith(INPUT_PREFIX):
            input_tabs.append(name)
        elif name.startswith(OUTPUT_PREFIX):
            output_tabs.append(name)
        elif name.startswith(M_PREFIX):
            m_tabs.append(name)
        else:
            calc_tabs.append(name)
    return {
        "input_tabs": input_tabs, "output_tabs": output_tabs,
        "m_tabs": m_tabs, "calc_tabs": calc_tabs,
    }
```

Update `validate_template` to take a `role` param: `"model"` | `"assumption_pack"` | `"output_template_xlsx"` and validate per [tab_prefix_contract.md § Per-entity rules](../architecture/tab_prefix_contract.md).

Add tests in `test_excel_template_engine.py`.

---

### A-003 · `OutputTemplate` Pydantic model + Firestore (S)

**File**: `backend/app/models/output_template.py`

```python
class OutputTemplateCreate(BaseModel):
    name: str
    code_name: str = ""
    description: str = ""
    format: Literal["xlsx"] = "xlsx"  # PDF/docx/gdoc in later sprints

class OutputTemplateResponse(BaseModel):
    id: str
    name: str
    code_name: str
    description: str
    format: str
    version: int
    storage_kind: str  # always "drive_xlsx" for now
    drive_file_id: str | None
    drive_revision_id: str | None
    m_tabs: list[str]
    output_tabs: list[str]
    calc_tabs: list[str]
    size_bytes: int
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
```

Firestore collection: `{prefix}output_templates/{templateId}`.

---

### A-004 · `Run` top-level Firestore model (S)

**File**: `backend/app/models/run.py`

```python
class RunCreate(BaseModel):
    project_id: str
    assumption_pack_id: str
    model_id: str
    output_template_id: str

class RunResponse(BaseModel):
    id: str
    project_id: str
    assumption_pack_id: str
    assumption_pack_version: int
    model_id: str
    model_version: int
    output_template_id: str
    output_template_version: int
    status: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    output_drive_file_id: str | None
    output_download_url: str | None
    warnings: list[str]
    error: str | None
    triggered_by: str
```

Firestore collection: `{prefix}runs/{runId}` (top-level, not nested under project).

---

### A-005 · `services/run_validator.py` — three-way checker (S)

**File**: `backend/app/services/run_validator.py`

```python
def validate_run_composition(
    model: dict,
    pack: dict,
    output_template: dict,
) -> list[str]:
    """Return [] if compatible, else a list of human-readable error strings."""
    errors = []
    
    # Rule 1: AssumptionPack provides every Model input
    missing = set(model["input_tabs"]) - set(pack["input_tabs"])
    if missing:
        errors.append(f"AssumptionPack missing required input tabs: {sorted(missing)}")
    
    # Rule 2: AssumptionPack contains only I_ tabs (already enforced at upload, defensive)
    if pack.get("output_tabs") or pack.get("m_tabs") or pack.get("calc_tabs"):
        errors.append("AssumptionPack must contain only I_ tabs")
    
    # Rule 3: M_<name> tabs ↔ O_<name> tabs
    model_basenames = {t.removeprefix("O_") for t in model["output_tabs"]}
    template_basenames = {t.removeprefix("M_") for t in output_template["m_tabs"]}
    missing_outputs = template_basenames - model_basenames
    if missing_outputs:
        errors.append(
            f"OutputTemplate requires Model outputs not present: "
            f"{sorted('O_' + b for b in missing_outputs)}"
        )
    return errors
```

Tests: `tests/test_run_validator.py` covering all three rules with Hello World fixtures.

---

### A-006 · `services/run_executor.py` — two-stage pipeline (M)

**File**: `backend/app/services/run_executor.py`

Implements the algorithm in [run_pipeline.md § Algorithm](../architecture/run_pipeline.md):

```python
def execute_run_sync(
    model_bytes: bytes,
    pack_bytes: bytes,
    output_template_bytes: bytes,
    output_template_format: str,
) -> dict:
    """Returns {output_bytes, warnings, recalculated_stage1, recalculated_stage2}."""
    # Stage 1
    merged_model, warnings_1 = engine.overlay_scenario_on_template(model_bytes, pack_bytes)
    recalced_model = excel_engine.recalculate_with_libreoffice(merged_model)
    model_outputs = extract_model_outputs(recalced_model)
    
    # Stage 2 (only xlsx for now; future: dispatch by format)
    if output_template_format == "xlsx":
        artifact, warnings_2 = render_xlsx_output(output_template_bytes, model_outputs)
    else:
        raise NotImplementedError(f"Output format {output_template_format} not yet supported")
    
    return {
        "output_bytes": artifact,
        "warnings": warnings_1 + warnings_2,
        "recalculated_stage1": recalced_model is not None,
    }
```

`extract_model_outputs(recalced_model_bytes) -> dict[str, dict[str, Any]]`:
- Open with `data_only=True`
- For each `O_*` tab, build `{cell_ref → value}` dict

`render_xlsx_output(template_bytes, model_outputs) -> tuple[bytes, list[str]]`:
- Open template
- For each `M_<name>` tab, look up `O_<name>` in model_outputs
- Cell-copy the values
- Save → recalc → return

Tests: `tests/test_run_executor.py` with Hello World end-to-end. Assert output cells equal expected values.

---

### A-007 · Backend router `output_templates.py` (S)

**File**: `backend/app/routers/output_templates.py`

Mirrors `excel_templates.py`:
- `POST /api/output-templates` — multipart upload, classify, store in Drive
- `GET /api/output-templates` — list (summary)
- `GET /api/output-templates/{id}` — detail
- `GET /api/output-templates/{id}/download` — Drive URL
- `PUT /api/output-templates/{id}` — metadata update
- `DELETE /api/output-templates/{id}`

Storage: Drive only (no GCS for OutputTemplates either). Folder: `<root>/MastekoFM/OutputTemplates/`.

---

### A-008 · Backend router `runs.py` (S)

**File**: `backend/app/routers/runs.py`

```
POST   /api/runs                              create + execute synchronously (Sprint C makes this async)
GET    /api/runs                              list (filter: project_id, status)
GET    /api/runs/{run_id}                     detail
POST   /api/runs/{run_id}/retry               new run with same composition
GET    /api/projects/{project_id}/runs        per-project list
```

POST handler:
1. Load model, pack, output_template
2. Run `run_validator.validate_run_composition`
3. If errors → 400 with `{errors: [...]}`
4. Create Run doc with `status="running"`
5. Execute synchronously (Sprint C will enqueue instead)
6. Update Run with results
7. Return RunResponse

---

### A-009 · `/api/seed/helloworld` endpoint (S)

**File**: `backend/app/routers/seed.py` (new — replaces `excel_seed.py`)

```python
@router.post("/api/seed/helloworld")
def seed_helloworld(current_user: CurrentUser):
    """Idempotent: returns existing IDs if already seeded."""
    # 1. Read seed files from seed/helloworld/
    # 2. Upload helloworld_model.xlsx as a Model
    # 3. Upload helloworld_inputs.xlsx as an AssumptionPack
    # 4. Upload helloworld_report.xlsx as an OutputTemplate
    # 5. Create Project "Hello World"
    # 6. Return all IDs
```

Use `pkg_resources` or `Path(__file__).parent / "../../seed/helloworld/"` to locate files.

Keep the existing `excel_seed.py` working for Campus Adele until Sprint B replaces it.

---

### A-010 · Frontend `OutputTemplatesPage.tsx` (S)

**File**: `frontend/src/pages/OutputTemplatesPage.tsx`

Mirror `ExcelTemplatesPage.tsx`:
- List with name, code_name, format, version, M_ tab count, O_ tab count
- Upload form (name, code_name, description, file)
- Delete button

Add nav item in `Layout.tsx`: "Output Templates" between "Models" and "Settings".

---

### A-011 · Frontend `NewRunModal.tsx` (M) ⭐ centerpiece

**File**: `frontend/src/components/NewRunModal.tsx`

Three-dropdown modal:

```
┌────────────────────────────────────────┐
│ + New Run for Hello World              │
├────────────────────────────────────────┤
│                                        │
│  Inputs:    [Hello World Inputs ▾]     │  ← scoped to project's AssumptionPacks
│  Model:     [Hello World Model ▾]      │  ← workspace-wide, filtered for compat
│  Output:    [Hello World Report ▾]     │  ← workspace-wide, filtered for compat
│                                        │
│  ✅ Compatible — ready to run          │
│                                        │
│           [Cancel]    [▶ Run]          │
└────────────────────────────────────────┘
```

Behavior:
- On open, fetch all eligible AssumptionPacks for the project, all Models, all OutputTemplates
- When any dropdown changes, re-validate via a new endpoint `POST /api/runs/validate` (or client-side from the entity metadata) and update the other dropdowns to grey out incompatible options
- Submit button disabled until all three are picked AND validation passes
- On Run → POST /api/runs → poll for status (Sprint C makes this real-time) → close modal and navigate to RunDetailPage

Component: `CompatibilityBadge.tsx` — green ✅ "Compatible" or red ❌ "AssumptionPack missing tab `I_Foo`".

---

### A-012 · Frontend `RunsPage.tsx` + `RunDetailPage.tsx` (S)

**Files**: `frontend/src/pages/RunsPage.tsx`, `frontend/src/pages/RunDetailPage.tsx`

`RunsPage`: filterable list of all Runs (project, model, output template, status, started_at, duration, output download).

`RunDetailPage`: full Run record + 3-way composition + download links + retry button + warnings/errors.

Add routes in `App.tsx`:
- `/runs`
- `/runs/:runId`
- `/output-templates`

---

### A-013 · Backend tests (S)

**Files**:
- `tests/test_run_validator.py` — ~6 tests covering all three rules
- `tests/test_run_executor.py` — Hello World end-to-end + edge cases (compatibility errors, missing files)
- Update `tests/test_excel_template_engine.py` — add `m_tabs` cases
- Update `tests/fixtures/` — add Hello World files

Target: ~10 new tests; total 112+ all green.

---

### A-014 · Layout nav refresh (XS)

**File**: `frontend/src/components/Layout.tsx`

Rename "Excel Projects" → "Projects" (and the entity rename happens in Sprint B; the label can change now).

Add nav items in order:
- Projects
- Models (renamed from Excel Templates)
- Output Templates (NEW)
- Runs (NEW)
- Settings

Keep all legacy nav behind `?legacy=1` exactly as it is.

---

### A-015 · Deploy + smoke test (XS)

1. `./deploy-dev.sh` → bumps to v1.035 (or higher)
2. Verify health: `/health` → 200, `/api/health/full` → ok
3. Hit `/api/seed/helloworld` from a curl with a real Google token (via UI)
4. Open the UI, navigate to Hello World project, click "+ New Run"
5. Pick the three dropdowns, submit
6. Verify output file: open in Excel, check `O_Report` cells = 12, 35, 47
7. Update [SESSION_HANDOFF.md](../../SESSION_HANDOFF.md) with what's live

---

## Data model added

```
{prefix}output_templates/{templateId}      -- new top-level
{prefix}runs/{runId}                       -- new top-level
```

The existing `{prefix}excel_templates/{id}`, `{prefix}excel_projects/{id}/scenarios/{id}/runs/{id}` collections all stay alive for now. Sprint B migrates them away.

---

## API additions

```
POST   /api/output-templates                                multipart upload
GET    /api/output-templates                                list
GET    /api/output-templates/{id}
GET    /api/output-templates/{id}/download
PUT    /api/output-templates/{id}
DELETE /api/output-templates/{id}

POST   /api/runs                                            launch a Run
GET    /api/runs                                            global list
GET    /api/runs/{id}                                       detail
POST   /api/runs/{id}/retry                                 new run, same composition
GET    /api/projects/{project_id}/runs                      per-project list

POST   /api/runs/validate                                   check compatibility (used by UI dropdowns)
POST   /api/seed/helloworld                                 idempotent seed
```

---

## Risks

| Risk | Mitigation |
|---|---|
| Two-stage LibreOffice recalc takes too long | Hello World should be <2s; if not, profile `excel_engine` for redundant work |
| Compatibility validator wrong on real models | Test with Campus Adele after Sprint B re-seed; for now Hello World is the proof |
| `M_*` cell-copy doesn't preserve formulas | Same engine as I_ overlay; if it works for I_ it works for M_ |
| Run becoming async (Sprint C) breaks the modal flow | Design the modal to handle both sync and async response shapes from day one |
| Browser caches old bundle | Already fixed in v1.034 (no-cache index.html) |

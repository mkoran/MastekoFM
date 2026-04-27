# MastekoFM — Architecture

> Last reviewed: 2026-04-16
> Status: in-flight redesign (see [docs/REDESIGN_2026_04.md](docs/REDESIGN_2026_04.md))
> Implementation phase: about to start Sprint A (Hello World vertical slice)

---

## 1. What MastekoFM is

A **financial modeling operating system**.

A SaaS platform that separates the three independently-versioned things a financial model is made of:

1. **Assumptions** (the numbers and tables a user wants to model)
2. **Model** (the spreadsheet-based computation engine)
3. **Output Template** (the shape of the report a user wants to produce)

Users compose a **Run** by picking one of each — `(AssumptionPack vN, Model vM, OutputTemplate vO)` — and the platform produces a versioned, downloadable, fully reproducible output artifact.

### What this is NOT

- ❌ Spreadsheet management
- ❌ A platform for editing Excel files
- ❌ A spreadsheet-as-database tool

Excel is **just the calculation engine**. Source of truth lives in the Firestore metadata + Drive files versioned alongside it.

---

## 2. The three-way model

```
                    AssumptionPack
                  (the numbers user wants to model)
                          │
                          ▼ overlay I_ tabs
                        Model
                  (the .xlsx with calculation logic)
                          │
                          ▼ extract O_ tabs
                    OutputTemplate
                  (the report layout / format)
                          │
                          ▼ recalc + render
                       Output
                  (the .xlsx / PDF / .docx / Google Doc artifact)
```

Composition happens **per Run**, not at design time. An AssumptionPack is not bound to any particular Model. A Model is not bound to any particular OutputTemplate. The validator decides at Run time whether a `(pack, model, template)` triple is compatible.

See [docs/architecture/three_way_composition.md](docs/architecture/three_way_composition.md) for the full pattern.

---

## 3. Tab-prefix contract (the engine convention)

Every `.xlsx` file MastekoFM touches obeys these case-sensitive prefixes:

| Prefix | Meaning | Used on |
|---|---|---|
| `I_*` | **I**nput tab — filled by an AssumptionPack | Model, AssumptionPack |
| `O_*` | **O**utput tab — published by a Model for downstream use | Model |
| `M_*` | **M**odel-output tab — filled by a Model's `O_*` values | OutputTemplate only |
| (other) | Calculation tab — formulas only, never touched | Model, OutputTemplate |

Case sensitivity is strict — `i_Cap Table` is a calc tab, NOT an input.

The full contract — naming, what's allowed, what to avoid — lives in [docs/architecture/tab_prefix_contract.md](docs/architecture/tab_prefix_contract.md).

---

## 4. Run pipeline

Two-stage overlay-and-recalc, driven by the same `excel_template_engine.overlay_tab` primitive at each stage:

```
Stage 1 (Model)
  Read Model template .xlsx
  Overlay AssumptionPack's I_* tabs onto Model's I_* tabs
  LibreOffice recalc
  Read Model.O_* tab values

Stage 2 (Output)
  Read OutputTemplate .xlsx
  For each M_<name> tab in OutputTemplate, overlay matching O_<name> values from stage 1
  LibreOffice recalc
  Save OutputTemplate workbook → final artifact
```

Full algorithm with code references in [docs/architecture/run_pipeline.md](docs/architecture/run_pipeline.md).

---

## 5. Entities & data model

### Firestore collections (post-Sprint-B cleanup)

```
{prefix}models/{modelId}                  -- versioned .xlsx with I_/O_/calc tabs
{prefix}output_templates/{templateId}     -- versioned .xlsx (M_/calc/O_) or PDF/Word/Sheets template
{prefix}projects/{projectId}              -- thin org scope: members, drive folder, defaults
{prefix}projects/{pid}/assumption_packs/  -- versioned .xlsx (I_ tabs only) per project
{prefix}runs/{runId}                      -- top-level: every run across all projects
```

### Per-entity required fields

```
Model {
  id, name, code_name, description, version, status
  storage_kind: "drive_xlsx" (only)
  drive_file_id
  input_tabs:  [tab names of I_*]      // declarative schema
  output_tabs: [tab names of O_*]
  calc_tabs:   [tab names of other]
  size_bytes, uploaded_by, created_at, updated_at
}

OutputTemplate {
  id, name, code_name, description, version, status
  format: "xlsx"  // future: "pdf" | "docx" | "google_doc"
  storage_kind: "drive_xlsx"
  drive_file_id
  m_tabs:      [tab names of M_*]      // model outputs this template needs
  output_tabs: [tab names of O_*]      // final artifact-shaping tabs
  calc_tabs:   [tab names of other]
}

Project {
  id, name, code_name, description
  drive_folders: { project, inputs, outputs, models?, output_templates? }
  default_model_id?      // optional: default to pre-select in Run modal
  members: [{ uid, role, added_at }]   // owner | editor | viewer
  status: "active" | "archived"
}

AssumptionPack {
  id, project_id, name, code_name, description, version
  storage_kind: "drive_xlsx"
  drive_file_id
  input_tabs: [tab names of I_*]
  status: "active" | "archived"
}

Run {
  id, project_id
  assumption_pack_id, assumption_pack_version
  model_id, model_version
  output_template_id, output_template_version
  status: "pending" | "running" | "completed" | "failed"
  started_at, completed_at, duration_ms
  output_drive_file_id, output_download_url
  warnings: [...], error?, retry_of?
  triggered_by: <uid>
}
```

### Composition validity

A Run is launchable iff:

1. AssumptionPack's `input_tabs` ⊇ Model's `input_tabs` (every Model input is provided)
2. OutputTemplate's `m_tabs` ⊆ {strip(`O_`, t) for t in Model's `output_tabs`} (every M_ tab has a matching Model output)

The validator service is `services/run_validator.py`.

---

## 6. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend API | Python 3.12 + FastAPI | Existing, fast, well-typed |
| Workers (async runs) | Same image, separate Cloud Run service | Single deploy, isolated CPU |
| Excel engine | **openpyxl** (read/write) + **LibreOffice headless** (recalc) | Cloud-Run friendly, no Excel license, full formula compat (XIRR/XNPV/IRR/etc.) |
| Auth | Firebase Auth (Google Sign-In) | Already in production |
| Database | Firestore | Existing, good fit, real-time listeners free |
| File storage | Google Drive (`.xlsx` files) + GCS (output blobs) | Drive for human editing in Sheets Office mode; GCS for stable download URLs |
| Job queue | Cloud Tasks | GCP-native, no extra infra |
| Frontend | React 19 + TypeScript + Vite + Tailwind | Existing |
| Hosting | Firebase Hosting | Existing |
| CI/CD | Cloud Build → Cloud Run + Firebase | Existing, working |
| Output renderers | xlsx (built-in), WeasyPrint (PDF), python-docx (Word), Google Docs API | Each format = one renderer module |

### Push-back from earlier draft spec

The original specification suggested xlwings, PostgreSQL, and Redis. We keep:
- **LibreOffice over xlwings** — cloud-friendly, no Excel license, no Windows VMs
- **Firestore over Postgres** — existing, scales, real-time listeners free
- **Cloud Tasks over Redis** — managed, no infra, integrates with Cloud Run

Decision rationale: [docs/REDESIGN_2026_04.md § "Where I'd push back"](docs/REDESIGN_2026_04.md).

---

## 7. Storage strategy

```
Drive layout:
  <user-picked-root>/MastekoFM/
    Models/
      <model_code>_v<N>.xlsx
    OutputTemplates/
      <template_code>_v<N>.xlsx
    Projects/
      <project_code>/
        Inputs/
          <pack_code>.xlsx
        Outputs/
          <timestamp>_<run_id>.xlsx

GCS layout (masteko-fm-outputs bucket, public read):
  runs/<run_id>/<timestamp>_<output_filename>.xlsx
```

- **Drive holds canonical files** — Models, OutputTemplates, AssumptionPacks. Edited via Sheets Office mode.
- **GCS holds output mirrors** — stable HTTPS URLs for downloads and link sharing.
- **Drive revisions are the version history** — we record `drive_revision_id` on every Run for full reproducibility.

---

## 8. Async run lifecycle

```
1. POST /api/runs    body: { project_id, model_id, pack_id, output_template_id }
                     → 202 Accepted, returns { run_id }
                     → creates Firestore doc { status: pending }
                     → enqueues to Cloud Tasks queue mfm-runs

2. Cloud Tasks delivers task to worker Cloud Run service
                     → updates run.status = running
                     → executes Stage 1 + Stage 2 (see Run Pipeline)
                     → uploads output to Drive + GCS
                     → updates run.status = completed (or failed + error)

3. Frontend polls GET /api/runs/{run_id} OR uses Firestore onSnapshot for live updates

4. Failed runs retry automatically (Cloud Tasks exponential backoff, max 3 attempts).
   Final failure leaves status: failed with error message.
   User can manually retry via POST /api/runs/{run_id}/retry → creates a new run with same composition.
```

---

## 9. Project structure

```
MastekoFM/
├── README.md                           — top-level pitch
├── ARCHITECTURE.md                     — this file
├── BACKLOG.md                          — sprints + stories
├── CLAUDE.md                           — development rules (mandatory)
├── LESSONS_LEARNED.md                  — bugs, gotchas, hard-won lessons
├── SESSION_HANDOFF.md                  — current state for the next dev/agent
├── VERSION                             — MAJOR.NNN, auto-bumped on DEV deploy
│
├── backend/
│   ├── Dockerfile                      — multi-stage, includes LibreOffice
│   ├── requirements.txt
│   └── app/
│       ├── main.py                     — FastAPI app + router registration
│       ├── config.py                   — settings, Firestore client
│       ├── middleware/
│       │   └── auth.py                 — Firebase Auth + DEV bypass
│       ├── models/                     — Pydantic schemas (NO business logic)
│       │   ├── model.py                — Model entity (ex-ExcelTemplate)
│       │   ├── output_template.py      — OutputTemplate entity (NEW)
│       │   ├── project.py              — Project entity (slim)
│       │   ├── assumption_pack.py      — AssumptionPack entity (ex-Scenario)
│       │   ├── run.py                  — Run entity (top-level)
│       │   └── user.py
│       ├── routers/                    — HTTP endpoints, thin
│       │   ├── models.py               — Model CRUD
│       │   ├── output_templates.py     — OutputTemplate CRUD
│       │   ├── projects.py             — Project CRUD + member mgmt
│       │   ├── assumption_packs.py     — AssumptionPack CRUD + Edit-in-Sheets
│       │   ├── runs.py                 — POST/GET runs, retry, list per project
│       │   ├── seed.py                 — /api/seed/helloworld, /api/seed/campus-adele
│       │   ├── auth.py
│       │   ├── health.py
│       │   └── settings.py             — workspace defaults, drive folder
│       ├── services/                   — business logic
│       │   ├── excel_template_engine.py — classify/extract/overlay/validate
│       │   ├── excel_engine.py         — LibreOffice recalc (low-level)
│       │   ├── run_validator.py        — three-way compatibility checker (NEW)
│       │   ├── run_executor.py         — two-stage Stage1+Stage2 pipeline (NEW)
│       │   ├── pack_store.py           — Drive AssumptionPack adapter (was scenario_store)
│       │   ├── output_renderers/       — one renderer per output format (NEW)
│       │   │   ├── xlsx_renderer.py
│       │   │   ├── pdf_renderer.py     — Sprint D
│       │   │   ├── docx_renderer.py    — Sprint H
│       │   │   └── gdoc_renderer.py    — Sprint H
│       │   ├── storage_service.py      — GCS helper
│       │   └── drive_service.py        — Google Drive ops
│       └── workers/                    — async processors (Sprint C)
│           └── run_worker.py           — Cloud Tasks handler for /tasks/run/{id}
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── App.tsx                     — Router
│       ├── pages/
│       │   ├── ProjectsPage.tsx        — list of Projects
│       │   ├── ProjectView.tsx         — single project + AssumptionPacks + Runs + "+ New Run" modal
│       │   ├── ModelsPage.tsx          — list/upload Models
│       │   ├── OutputTemplatesPage.tsx — list/upload OutputTemplates
│       │   ├── RunsPage.tsx            — global runs dashboard (Sprint C)
│       │   ├── RunDetailPage.tsx       — single run + outputs + retry
│       │   ├── SettingsPage.tsx
│       │   └── Login.tsx
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── ProtectedRoute.tsx
│       │   ├── NewRunModal.tsx         — the 3-dropdown composer (NEW)
│       │   └── CompatibilityBadge.tsx  — green/red indicator (NEW)
│       ├── services/
│       │   ├── api.ts                  — fetch wrapper, token-wait, X-MFM-Drive-Token
│       │   └── firebase.ts
│       └── contexts/
│           └── AuthContext.tsx
│
├── seed/                               — committed seed files (Sprint B)
│   ├── helloworld/
│   │   ├── helloworld_model.xlsx       — minimal Model (I_Numbers, O_Results)
│   │   ├── helloworld_inputs.xlsx      — minimal AssumptionPack
│   │   ├── helloworld_report.xlsx      — minimal OutputTemplate (M_Results, O_Report)
│   │   └── README.md                   — explains the file structure
│   └── campus_adele/
│       ├── campus_adele_model.xlsx     — the 15-tab construction-to-perm Model
│       ├── campus_adele_base_pack.xlsx — Base Case AssumptionPack
│       ├── campus_adele_summary.xlsx   — investor summary OutputTemplate
│       └── README.md
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── helloworld_model.xlsx       — engine regression fixture
│   │   ├── helloworld_inputs.xlsx
│   │   ├── helloworld_report.xlsx
│   │   └── campus_adele.xlsx
│   ├── test_excel_template_engine.py
│   ├── test_run_validator.py           — Sprint A
│   ├── test_run_executor.py            — Sprint A
│   ├── test_pack_store.py              — renamed from test_scenario_store
│   ├── test_models_router.py
│   ├── test_output_templates_router.py — Sprint A
│   ├── test_runs_router.py             — Sprint A
│   ├── test_projects_router.py
│   ├── test_auth.py
│   └── test_health.py
│
├── docs/
│   ├── REDESIGN_2026_04.md             — strategic context for the redesign
│   ├── architecture/
│   │   ├── three_way_composition.md
│   │   ├── tab_prefix_contract.md
│   │   └── run_pipeline.md
│   └── sprints/
│       ├── SPRINT_A_helloworld_slice.md
│       ├── SPRINT_B_cleanup_and_migration.md
│       ├── SPRINT_C_async_runs.md
│       ├── SPRINT_D_pdf_outputs.md
│       ├── SPRINT_E_multi_user.md
│       ├── SPRINT_F_json_assumptions.md
│       ├── SPRINT_G_sensitivity_sweeps.md
│       └── SPRINT_H_word_googledocs.md
│
├── firebase.json                       — hosting config (no-cache index, immutable assets)
├── cloudbuild.yaml                     — Docker build + deploy
├── deploy-dev.sh                       — VERSION bump + Cloud Build + Firebase deploy
├── deploy-prod.sh                      — promote DEV image to prod (no version bump)
└── pyproject.toml                      — Python deps + ruff + pytest config
```

---

## 10. Environments

| Environment | Backend | Frontend | Firestore prefix | Auth |
|---|---|---|---|---|
| LOCAL | localhost:8080 | localhost:5173 | `dev_` | DEV bypass |
| DEV | masteko-fm-api-dev (Cloud Run) | dev-masteko-fm.web.app | `dev_` | Firebase Auth or DEV bypass |
| PROD | masteko-fm-api-prod (Cloud Run) | masteko-fm.web.app | `prod_` | Firebase Auth only |

DEV is recoverable; PROD is not. See CLAUDE.md "Standing Authorizations" for the full asymmetry.

---

## 11. Compatibility-validation rules (canonical)

```python
def validate_run(model: Model, pack: AssumptionPack, output_template: OutputTemplate) -> list[str]:
    errors = []
    
    # Rule 1: AssumptionPack must provide every Model input
    missing_inputs = set(model.input_tabs) - set(pack.input_tabs)
    if missing_inputs:
        errors.append(f"AssumptionPack missing required input tabs: {sorted(missing_inputs)}")
    
    # Rule 2: AssumptionPack may not contain O_ or M_ tabs
    pack_classes = classify_bytes(pack.bytes)
    if pack_classes["output_tabs"] or pack_classes.get("m_tabs"):
        errors.append("AssumptionPack must contain only I_ tabs")
    
    # Rule 3: Every M_<name> in OutputTemplate must match an O_<name> in Model
    model_output_basenames = {tab.removeprefix("O_") for tab in model.output_tabs}
    template_m_basenames = {tab.removeprefix("M_") for tab in output_template.m_tabs}
    missing_outputs = template_m_basenames - model_output_basenames
    if missing_outputs:
        errors.append(f"OutputTemplate requires Model outputs not present: {sorted(missing_outputs)}")
    
    return errors
```

UI: dropdowns in the New Run modal show only compatible options. Submit button disabled if any errors.

---

## 12. Versioning & reproducibility

Each entity has a `version` integer. Each artifact has a `drive_revision_id` from Drive's built-in version history.

Every Run records:
- `model_id`, `model_version`, `model_drive_revision_id`
- `assumption_pack_id`, `assumption_pack_version`, `pack_drive_revision_id`
- `output_template_id`, `output_template_version`, `output_template_drive_revision_id`
- `output_drive_file_id`, `output_drive_revision_id`

Reproducibility test: given a Run record, fetch all three input files at the recorded revisions, re-execute the pipeline, byte-compare the output. Should produce identical bytes (modulo timestamps in cell metadata, which the engine zeros out).

---

## 13. Standing decisions

Pulled together so a new dev sees them in one place. Full context in [docs/REDESIGN_2026_04.md](docs/REDESIGN_2026_04.md).

| # | Decision | Why |
|---|---|---|
| 1 | Excel via LibreOffice headless, NOT xlwings | Cloud Run, no Excel license, full formula compat |
| 2 | Firestore for metadata, NOT Postgres | Existing, scales, real-time, no migration burden |
| 3 | Cloud Tasks for queue, NOT Redis | GCP-native, managed, integrates with Cloud Run |
| 4 | Drive (not GCS) for canonical AssumptionPack storage | Edit-in-Sheets UX, version history, sharing |
| 5 | GCS for output blob hosting | Stable public URLs |
| 6 | Tab prefixes are CASE-SENSITIVE | `i_Cap Table` is calc, `I_Cap Table` is input |
| 7 | Three prefixes: `I_*`, `O_*`, `M_*` (+ calc) | Disambiguates pack inputs vs model outputs vs template inputs |
| 8 | OutputTemplate is just another `.xlsx` with `M_*` + calc + `O_*` | Reuses 100% of existing engine; no new render path needed for `xlsx` format |
| 9 | Three-way composition validated per Run | Prevents incompatible runs at submit time |
| 10 | Async via Cloud Tasks (Sprint C+) | Required for 100+ concurrent + sensitivity sweeps |
| 11 | Custom header `X-MFM-Drive-Token`, NOT `X-Google-*` | Fastly/Firebase Hosting strips `X-Google-*` headers |
| 12 | `firebase.json` sets `Cache-Control: no-cache` on index.html, immutable on `/assets/**` | Stale-bundle bug after deploy |
| 13 | OAuth scope = `drive.file` only (non-sensitive) | No Google verification required, app available to any domain |
| 14 | OAuth consent: External + In Production | Multi-domain users without test-user list |
| 15 | API client polls for token up to 3s before request | Fixes Firebase `onAuthStateChanged` race |

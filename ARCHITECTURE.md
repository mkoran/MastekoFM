# MastekoFM — Financial Modelling Platform

## Product vision

MastekoFM is a SaaS platform where users create **projects**, connect **data sources**, and build chains of **linked spreadsheets** — each sheet's outputs feeding into the next sheet's assumptions. The platform produces **versioned financial models** and **automated PDF reports** from any combination of inputs.

It is model-agnostic: the same engine supports DCF, 3-statement, project finance, waterfall distributions, or any custom structure. The model type emerges from how the user wires their sheets together.

---

## Core concepts

### Project
A project is the top-level container. It has a name, an owner, collaborators, and a version history. Everything below belongs to a project.

### Data source
A data source is a connection to external data that provides **input values** to the system. Supported source types:

| Source type | Connection method | Refresh |
|---|---|---|
| Airtable | API key + base ID | On-demand / scheduled |
| Excel file | Upload to Google Drive | On re-upload |
| CSV file | Upload to Google Drive | On re-upload |
| Google Sheets | OAuth + sheet ID | On-demand / scheduled |
| Manual entry | In-app form | Immediate |
| API endpoint | URL + auth config | On-demand / scheduled |
| Previous sheet output | Internal DAG link | Automatic |

Each data source produces a flat key-value map of **named inputs**. Example: an Airtable base might produce `{land_cost: 2500000, unit_count: 48, avg_rent: 1850}`.

### Assumptions layer
The assumptions layer is the bridge between raw data sources and spreadsheet calculations. It:

1. **Maps** raw source fields to named assumption keys
2. **Validates** types, ranges, and required fields
3. **Versions** every change (who changed what, when, why)
4. **Overrides** — a user can manually override any mapped value; the override is tracked separately from the source value

An assumption has:
- `key` — unique name within the project (e.g. `land_cost`)
- `value` — current resolved value
- `source` — which data source provided it (or "manual override")
- `type` — number, percentage, date, currency, text, boolean
- `category` — grouping for display (e.g. "Revenue", "Construction", "Financing")
- `version` — auto-incremented on change

### Spreadsheet (calculation node)
A spreadsheet is a calculation engine that:

1. **Declares inputs** — which assumption keys it reads
2. **Contains formulas** — rows and columns with cell-level formulas
3. **Declares outputs** — which cells are published as named outputs

Spreadsheets are stored as **versioned templates**. The template defines structure (rows, columns, formulas). The project instance fills it with actual assumption values.

**Key design decision: Excel-based engine.** Spreadsheets are `.xlsx` files with named ranges. The calculation pipeline:
1. `openpyxl` injects assumption values into named input cells
2. **LibreOffice headless** recalculates all formulas (full Excel formula compatibility including XIRR, XNPV, IRR, RATE, etc.)
3. `openpyxl` extracts output values from named output cells

Users can **download any sheet as a working Excel file**, edit formulas and structure in Excel, and re-upload. The platform validates that named ranges still exist and re-maps inputs/outputs. Each upload creates a new version of the sheet with full history.

### DAG (directed acyclic graph)
The spreadsheet waterfall is a DAG. Each node is a spreadsheet. Edges represent output→input mappings:

```
Sheet A (Revenue Model)
  outputs: {gross_revenue, net_revenue, vacancy_rate}
      ↓
Sheet B (Operating Expenses)
  inputs: {gross_revenue} ← from Sheet A
  outputs: {total_opex, noi}
      ↓
Sheet C (Financing)
  inputs: {noi} ← from Sheet B
  outputs: {debt_service, cash_after_debt}
      ↓
Sheet D (Returns Analysis)
  inputs: {cash_after_debt} ← from Sheet C, {land_cost} ← from Assumptions
  outputs: {irr, npv, equity_multiple, cash_on_cash}
```

The DAG is validated: no cycles allowed. When an upstream sheet recalculates, all downstream sheets recalculate in topological order.

### Report generator
Reports are PDF documents assembled from:
- A **report template** (layout, branding, section structure)
- **Data bindings** — which sheet outputs, assumptions, or computed values fill each section
- **Charts** — generated from sheet data, embedded as images
- **Static content** — cover pages, disclaimers, methodology notes

Report templates are versioned independently of spreadsheet templates.

---

## Technical architecture

### Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind | Firebase Hosting |
| Backend API | Python 3.12, FastAPI, Cloud Run | Stateless, horizontally scalable |
| Auth | Firebase Auth | Google Sign-In, email/password |
| App database | Firestore | Projects, users, orgs, DAG config, assumptions |
| Real-time sync | Firestore onSnapshot | Live updates to all connected users |
| File storage | Google Drive API | Excel templates, uploaded files, generated reports |
| Analytics | BigQuery | Usage metrics, calculation audit logs |
| Secrets | GCP Secret Manager | API keys, tokens |
| CI/CD | Cloud Build | pytest → Docker → deploy |
| PDF generation | WeasyPrint | HTML→PDF with branded templates |
| Excel engine | openpyxl + LibreOffice headless | openpyxl for I/O, LibreOffice for calculation |
| Task queue | Cloud Tasks | Async recalculation, report generation |

### GCP project

- **Project ID**: `masteko-fm` (new GCP project, separate from masteko-dwh)
- **Region**: `northamerica-northeast1` (Montréal)
- Follows the same environment pattern as MastekoDWH: LOCAL / DEV / PROD
- Own Cloud Run service, Firebase Hosting sites, Firestore database, BigQuery dataset

### Repository structure

```
MastekoFM/
├── CLAUDE.md                    # Development rules and policies
├── ARCHITECTURE.md              # This document
├── BACKLOG.md                   # Product backlog
├── SESSION_HANDOFF.md           # Context for Claude Code sessions
├── Makefile                     # Local dev commands
├── docker-compose.yml           # Local dev stack
├── cloudbuild.yaml              # CI/CD pipeline
├── deploy-dev.sh                # DEV deployment
├── deploy-prod.sh               # PROD deployment
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings, env, secrets
│   │   ├── middleware/
│   │   │   └── auth.py          # Firebase Auth (bypass in DEV)
│   │   ├── models/              # Pydantic schemas
│   │   │   ├── project.py
│   │   │   ├── datasource.py
│   │   │   ├── assumption.py
│   │   │   ├── spreadsheet.py
│   │   │   ├── dag.py
│   │   │   ├── report.py
│   │   │   └── user.py
│   │   ├── routers/
│   │   │   ├── health.py
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── datasources.py
│   │   │   ├── assumptions.py
│   │   │   ├── spreadsheets.py
│   │   │   ├── dag.py
│   │   │   └── reports.py
│   │   ├── services/
│   │   │   ├── datasource_sync.py    # Airtable, CSV, Excel ingestion
│   │   │   ├── assumption_engine.py  # Mapping, validation, versioning
│   │   │   ├── excel_engine.py       # openpyxl: inject, calculate, extract
│   │   │   ├── dag_executor.py       # Topological sort + cascade recalc
│   │   │   ├── report_generator.py   # HTML→PDF assembly
│   │   │   └── drive_service.py      # Google Drive file operations
│   │   └── connectors/
│   │       ├── airtable.py
│   │       ├── csv_connector.py
│   │       ├── excel_connector.py
│   │       ├── gsheets_connector.py
│   │       └── api_connector.py
│   └── tests/
│       ├── test_excel_engine.py
│       ├── test_dag_executor.py
│       ├── test_assumption_engine.py
│       └── test_datasource_sync.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx          # Project list
│   │   │   ├── ProjectView.tsx        # Single project workspace
│   │   │   ├── DAGEditor.tsx          # Visual DAG wiring
│   │   │   ├── AssumptionsTable.tsx   # Editable assumptions grid
│   │   │   ├── SpreadsheetView.tsx    # Sheet preview + input/output mapping
│   │   │   ├── DataSourceConfig.tsx   # Source connection setup
│   │   │   └── ReportBuilder.tsx      # Report template + preview
│   │   ├── components/
│   │   │   ├── dag/                   # DAG visualization (React Flow)
│   │   │   ├── tables/               # Data grids (TanStack Table)
│   │   │   └── charts/               # Recharts components
│   │   └── services/
│   │       └── api.ts                 # Backend API client
│   └── public/
│
├── templates/
│   ├── spreadsheets/                  # Versioned .xlsx templates
│   │   ├── revenue_model_v1.xlsx
│   │   ├── operating_expenses_v1.xlsx
│   │   └── returns_analysis_v1.xlsx
│   └── reports/                       # Report HTML/CSS templates
│       ├── investor_summary/
│       └── lender_package/
│
└── skills/                            # Claude Code skills
    ├── SKILL_excel_engine.md
    ├── SKILL_dag_execution.md
    ├── SKILL_datasource_connectors.md
    └── SKILL_report_generation.md
```

---

## Data model (Firestore)

### Collection: `projects`
```
projects/{projectId}
  name: string
  owner_uid: string
  org_id: string
  created_at: timestamp
  updated_at: timestamp
  version: number
  status: "active" | "archived"
  collaborators: [{uid, role, added_at}]
```

### Collection: `datasources`
```
projects/{projectId}/datasources/{sourceId}
  name: string
  type: "airtable" | "excel" | "csv" | "gsheets" | "manual" | "api"
  config: {
    // airtable: {base_id, table_name, api_key_secret}
    // excel: {drive_file_id, sheet_name}
    // csv: {drive_file_id}
    // gsheets: {spreadsheet_id, range}
    // api: {url, method, headers, auth_type}
  }
  field_mappings: [{source_field, assumption_key, transform?}]
  last_synced_at: timestamp
  sync_status: "idle" | "syncing" | "error"
  sync_error: string?
```

### Collection: `assumptions`
```
projects/{projectId}/assumptions/{assumptionId}
  key: string               # unique within project
  display_name: string
  category: string           # "Revenue", "Construction", etc.
  type: "number" | "percentage" | "currency" | "date" | "text" | "boolean"
  value: any                 # current resolved value
  source_id: string?         # datasource that provided it
  is_overridden: boolean
  override_value: any?
  override_by: string?       # uid
  override_at: timestamp?
  version: number
  created_at: timestamp
  updated_at: timestamp
```

### Subcollection: `assumption_history`
```
projects/{projectId}/assumptions/{assumptionId}/history/{historyId}
  version: number
  value: any
  previous_value: any
  changed_by: string         # uid or "system"
  changed_at: timestamp
  reason: string?            # "Manual override" | "Airtable sync" | etc.
```

### Collection: `spreadsheets`
```
projects/{projectId}/spreadsheets/{sheetId}
  name: string
  template_id: string        # reference to template registry
  template_version: number
  drive_file_id: string      # the actual .xlsx in Drive
  inputs: [{assumption_key, cell_reference}]
  outputs: [{cell_reference, output_key, label}]
  position: {x, y}          # for DAG visual layout
  last_calculated_at: timestamp
  calculation_status: "idle" | "calculating" | "error"
  output_values: {key: value} # cached output values
```

### Collection: `dag_edges`
```
projects/{projectId}/dag_edges/{edgeId}
  source_sheet_id: string
  source_output_key: string
  target_sheet_id: string
  target_assumption_key: string  # maps to an assumption that gets overridden
  created_at: timestamp
```

### Collection: `reports`
```
projects/{projectId}/reports/{reportId}
  name: string
  template_id: string
  template_version: number
  bindings: [{section_id, data_type, data_ref}]
  generated_at: timestamp?
  drive_file_id: string?     # generated PDF in Drive
  status: "draft" | "generating" | "ready" | "error"
```

### Collection: `templates` (global, not per-project)
```
templates/{templateId}
  name: string
  type: "spreadsheet" | "report"
  description: string
  version: number
  drive_file_id: string       # the template .xlsx or HTML
  inputs_schema: [{key, type, label, required, default?}]
  outputs_schema: [{key, type, label, cell_reference}]
  created_by: string
  created_at: timestamp
  changelog: [{version, date, notes}]
```

---

## Key workflows

### 1. Create a project
1. User creates project → Firestore doc created
2. Google Drive folder created: `MastekoFM/{project_name}/`
3. Subfolders: `sources/`, `spreadsheets/`, `reports/`
4. Default assumptions categories seeded

### 2. Connect a data source
1. User selects source type (Airtable, Excel, CSV, etc.)
2. Provides connection config (API key, file upload, etc.)
3. System fetches available fields
4. User maps source fields → assumption keys
5. Initial sync runs → assumption values populated
6. Subsequent syncs update values, creating history entries

### 3. Add a spreadsheet to the DAG
1. User selects a spreadsheet template (or uploads custom .xlsx)
2. Template is registered: inputs and outputs declared via named ranges
3. Sheet is added as a node in the project DAG
4. User maps: which assumptions feed into which input cells
5. User maps: which output cells are published as named outputs
6. Sheet positioned in DAG canvas

### 4. Wire sheets together
1. User draws an edge from Sheet A's output to Sheet B's input
2. System validates: no cycles, type compatibility
3. Edge stored in `dag_edges`
4. When Sheet A recalculates, its outputs become Sheet B's inputs

### 5. Recalculate the DAG
1. Triggered by: assumption change, data source sync, manual trigger
2. DAG executor performs topological sort
3. For each sheet in order:
   a. Collect inputs (from assumptions + upstream outputs)
   b. Open .xlsx template
   c. Inject values into named input cells
   d. Calculate (openpyxl formula evaluator or LibreOffice)
   e. Extract output values from named output cells
   f. Cache outputs in Firestore
   g. Publish outputs as inputs for downstream sheets
4. Calculation status tracked per sheet
5. Errors halt downstream propagation with clear error messages

### 6. Generate a report
1. User selects report template
2. Binds sections to data: assumption values, sheet outputs, computed metrics
3. System generates HTML from template + data
4. Converts to PDF (WeasyPrint)
5. Stores in Google Drive
6. User can download or share link

---

## Versioning strategy

### Three things are versioned:

1. **Templates** (spreadsheet + report)
   - Stored in GitHub under `templates/`
   - Each template has a version number
   - Projects reference a specific template version
   - Upgrading a project to a new template version is an explicit action

2. **Assumptions**
   - Every value change creates a history entry
   - Full audit trail: who, when, what, why
   - Point-in-time reconstruction: "what was the model on March 15?"

3. **Project snapshots**
   - A snapshot captures: all assumption values + all sheet outputs + DAG config
   - Snapshots are named (e.g., "Q1 2026 Base Case", "Sensitivity: +2% rates")
   - Snapshots enable scenario comparison

### GitHub versioning
- All application code versioned in `github.com/mkoran/MastekoFM`
- Template .xlsx files versioned in the repo under `templates/`
- CLAUDE.md, skills, and backlog in the repo root
- Follows same branching strategy as MastekoDWH: `main` → `dev` → feature branches

---

## Excel vs Google Sheets decision

**Recommendation: Excel (.xlsx) as the primary format.**

| Factor | Excel (.xlsx) | Google Sheets |
|---|---|---|
| Offline editing | Full support | Requires internet |
| Formula complexity | Full Excel formula set | Subset + Apps Script |
| File portability | Universal | Requires export |
| Programmatic access | openpyxl (mature, fast) | Sheets API (quota limits) |
| Template versioning | Git-friendly (binary but diffable with tools) | Version history in Drive |
| User familiarity | Industry standard for finance | Less common in finance |
| Calculation engine | Can use LibreOffice headless | Must use Sheets API |
| Storage | Google Drive (or any storage) | Must be in Google Drive |
| Multi-user editing | Not real-time | Real-time collaboration |

Excel wins on portability, formula support, and finance-industry familiarity. The platform stores .xlsx files in Google Drive for accessibility, but the calculation engine operates on the files programmatically — users never need to open Google Drive directly unless they want to.

---

## Sprint plan

### Sprint 0 — Infrastructure skeleton
- GCP project `masteko-fm` provisioned
- Firebase project + Auth configured
- Cloud Run service deployed (health check only)
- Firebase Hosting DEV + PROD sites
- Firestore database created
- BigQuery dataset created
- Google Drive root folder created
- GitHub repo initialized with full structure
- CLAUDE.md, Makefile, docker-compose, deploy scripts
- CI/CD pipeline (Cloud Build)
- Local dev environment working

### Sprint 1 — Core data model + project CRUD
- User registration + auth flow
- Project CRUD (create, list, view, archive)
- Google Drive folder auto-creation per project
- Assumptions CRUD with validation and history
- Assumptions table UI (editable data grid)
- Categories and grouping

### Sprint 2 — Data source connectors
- CSV connector (upload + parse + map)
- Excel connector (upload + parse + map)
- Airtable connector (API + field discovery + map)
- Data source configuration UI
- Field mapping UI (source field → assumption key)
- Sync trigger + status display

### Sprint 3 — Excel engine + DAG
- Template registry (upload .xlsx, declare inputs/outputs via named ranges)
- Excel engine: inject inputs → calculate → extract outputs
- DAG data model (nodes + edges)
- DAG executor (topological sort + cascade recalculation)
- DAG editor UI (React Flow — drag nodes, draw edges)
- Spreadsheet preview UI (read-only grid showing current values)

### Sprint 4 — Wiring and recalculation
- Output→input mapping (sheet outputs become downstream inputs)
- Full DAG recalculation on assumption change
- Calculation status tracking and error handling
- Assumption override (manual value overrides source value)
- Assumption version history UI (timeline view)

### Sprint 5 — Report generation
- Report template system (HTML/CSS templates with data bindings)
- Data binding UI (map sections to sheet outputs / assumptions)
- Chart generation (Recharts → PNG → embed in PDF)
- PDF generation (WeasyPrint or Puppeteer)
- Report storage in Google Drive
- Report list + download UI

### Sprint 6 — Versioning and scenarios
- Project snapshots (freeze all values at a point in time)
- Snapshot comparison (side-by-side diff of two scenarios)
- Template versioning (upgrade project to new template version)
- Assumption diff view (what changed between snapshots)

### Sprint 7 — Analysis tools
- Sensitivity analysis (vary one input, chart the output impact)
- Scenario manager (named sets of assumption overrides)
- Dashboard widgets (KPI cards, trend charts)
- Export: full model as a single .xlsx workbook

### Sprint 8+ — Multi-tenant SaaS features
- Organization / team management
- Role-based access control (owner, editor, viewer)
- Sharing and collaboration
- Billing integration
- API access for external integrations
- Google Sheets connector
- Custom API endpoint connector

---

## Skills for Claude Code

The following skills should be created in the repo under `skills/` and referenced in CLAUDE.md:

### SKILL_excel_engine.md
Best practices for working with openpyxl: reading/writing named ranges, formula evaluation strategies, handling currency/percentage formatting, error handling for circular references, template validation.

### SKILL_dag_execution.md
How to implement and test DAG operations: topological sort, cycle detection, cascade recalculation, error propagation, partial recalculation (only dirty nodes).

### SKILL_datasource_connectors.md
Patterns for building data source connectors: field discovery, type inference, mapping normalization, sync scheduling, error recovery, credential management via Secret Manager.

### SKILL_report_generation.md
PDF report generation patterns: HTML template design, data binding, chart embedding, WeasyPrint configuration, branded template structure, page numbering, table of contents.

---

## CLAUDE.md additions

The project CLAUDE.md should include all rules from MastekoDWH plus:

```markdown
## MastekoFM-specific rules

### Excel files
- All .xlsx operations use openpyxl
- Named ranges are the ONLY interface between the platform and spreadsheets
- Never hardcode cell references (A1, B2) — always use named ranges
- Template validation: every template must declare its inputs and outputs
- Formula calculation: prefer openpyxl's formula evaluator; fall back to LibreOffice headless

### DAG operations
- Always validate for cycles before adding edges
- Recalculation uses topological sort — never recursive
- Failed nodes do not halt the entire DAG — downstream nodes are marked "stale"
- All recalculations are logged to BigQuery with timing data

### Assumptions
- Every value change creates a history entry — no exceptions
- Override values are stored separately from source values
- Type validation runs before storage (e.g., percentage must be 0-1 or 0-100)

### Reports
- Reports are generated asynchronously via Cloud Tasks
- PDF generation must complete within 60 seconds
- All generated files go to Google Drive, never local disk in production
```

---

## Design decisions (resolved 2026-04-14)

### 1. Multi-user editing → Checkout model

Users must **check out** a project (or specific sheets/assumptions) before editing. While checked out, other users see the project in read-only mode with a banner showing who has it checked out. This prevents conflicts without the complexity of CRDTs or real-time merge.

**Checkout rules:**
- Checkout is per-project (not per-sheet) in v1. Per-sheet checkout is a future refinement.
- Checkout has an automatic expiry (configurable, default 2 hours) to prevent abandoned locks.
- Owner can force-release another user's checkout.
- Checkout is recorded in the audit trail (who, when, duration).
- Read access is always available — only writes require checkout.

**Data model addition:**
```
projects/{projectId}
  checkout: {
    user_uid: string | null
    user_name: string | null
    checked_out_at: timestamp | null
    expires_at: timestamp | null
  }
```

**API additions:**
- `POST /api/projects/{id}/checkout` — acquire checkout
- `POST /api/projects/{id}/checkin` — release checkout
- `POST /api/projects/{id}/force-release` — owner only, force-release
- All write endpoints return 423 Locked if project is checked out by another user

**Frontend:**
- Checkout banner at top of project workspace
- "Check out to edit" button when viewing read-only
- Auto-checkin prompt after period of inactivity
- Visual indicator in project list showing checked-out projects

### 2. Calculation engine → LibreOffice headless (always)

All spreadsheet calculations run through **LibreOffice headless**. This is the most reliable methodology — it handles every Excel formula including XIRR, XNPV, RATE, IRR, MIRR, and all financial functions without gaps.

**Architecture:**
- LibreOffice is installed in the backend Docker image
- Calculation flow: inject values via openpyxl → save temp .xlsx → open in LibreOffice headless → recalculate → save → read results via openpyxl
- openpyxl is used only for reading/writing cell values and named ranges, never for formula evaluation
- LibreOffice runs in a sandboxed subprocess with timeout (30 seconds max)
- Calculation results are cached — recalculation only happens when inputs change

**Docker image addition:**
```dockerfile
RUN apt-get update && apt-get install -y libreoffice-calc-nogui --no-install-recommends
```

**Performance considerations:**
- LibreOffice cold start: ~2-3 seconds. Mitigate with Cloud Run min-instances in PROD.
- For heavy DAGs (10+ sheets), calculations run sequentially per topological order — parallelism is a future optimization.
- Calculation timing logged to BigQuery for performance monitoring.

### 3. Template marketplace → Backlog (future)

Not in initial release. Added to backlog as Domain 15 for future sprints. Users can create and version their own templates; sharing across organizations comes later.

### 4. Real-time updates → WebSockets via Firestore listeners

Connected users see results update **live** when data sources sync or recalculations complete.

**Implementation:**
- Frontend uses **Firestore onSnapshot listeners** — no custom WebSocket server needed. Firestore's real-time sync is built-in and handles reconnection, offline, and scaling automatically.
- Listeners attached to:
  - `projects/{id}` — checkout status, project metadata
  - `projects/{id}/assumptions` — assumption value changes
  - `projects/{id}/spreadsheets` — calculation status and output values
  - `projects/{id}/dag_edges` — DAG structure changes
- Backend writes to Firestore after each calculation step → frontend picks up changes within ~1 second
- Calculation status indicators update in real-time on the DAG canvas (idle → calculating → done/error)

**No additional infrastructure required** — Firestore real-time listeners are part of the existing stack. This is a frontend-only implementation detail.

### 5. In-app spreadsheet editing → Yes, users modify Excel files

Users can **edit spreadsheet files directly** — the platform provides a workflow for modifying the Excel templates that power their model.

**Editing workflow (v1 — download/upload cycle):**
1. User clicks "Edit spreadsheet" on a DAG node
2. Platform downloads the current .xlsx (with injected values) to the user's machine
3. User opens in Excel, modifies formulas/structure
4. User re-uploads the modified .xlsx
5. Platform re-discovers named ranges (inputs/outputs may have changed)
6. User confirms any mapping changes
7. DAG recalculates with the updated sheet

**Future enhancement (v2 — in-browser editing):**
- Embed a lightweight spreadsheet component (e.g., Luckysheet, Handsontable, or SheetJS)
- Allow formula editing without leaving the browser
- This is a significant feature — added to backlog for Sprint 8+

**Key constraint:** Whether edited locally or in-browser, the platform always validates that:
- All declared input named ranges still exist
- All declared output named ranges still exist
- No circular references within the sheet
- File size is within limits (10MB max)

**Data model addition — sheet version tracking:**
```
projects/{projectId}/spreadsheets/{sheetId}/versions/{versionId}
  version: number
  drive_file_id: string          # the .xlsx for this version
  uploaded_by: string
  uploaded_at: timestamp
  inputs_schema: [{key, cell_reference}]
  outputs_schema: [{key, cell_reference, label}]
  change_notes: string?
  is_current: boolean
```

### 6. Airtable sync → Ingest only (push-back in backlog)

v1 is strictly **one-way ingestion** from Airtable into assumptions. Writing results back to Airtable is added to the backlog as a future connector feature.

**Backlog items added:**
- DS-015: Airtable write-back connector (push output values to Airtable table)
- DS-016: Configurable push-back mappings (which outputs → which Airtable fields)
- DS-017: Push-back trigger options (manual, on recalculation, scheduled)

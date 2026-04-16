# MastekoFM — Product Backlog

> Last updated: 2026-04-16
> Status: Excel Template MVP shipping on `epic/excel-template-mvp`

## Domain 19: Excel Template MVP (tab-prefix architecture)

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| XT-001 | Excel Template upload + I_/O_/calc classification | P0 | A | shipped |
| XT-002 | GCS storage_service helper | P0 | A | shipped |
| XT-003 | excel_template_engine: classify / extract / overlay / validate | P0 | A | shipped |
| XT-004 | Routers: /api/excel-templates, /api/excel-projects, /api/scenarios | P0 | A | shipped |
| XT-005 | /api/excel-seed/campus-adele one-shot seed endpoint | P0 | A | shipped |
| XT-006 | Frontend pages: ExcelTemplates, ExcelProjects, ExcelProjectView | P0 | A | shipped |
| XT-007 | Hide legacy TGV nav (query flag `?legacy=1` to re-enable) | P0 | A | shipped |
| XT-008 | 17 new backend tests against real Campus Adele fixture | P0 | A | shipped |
| XT-009 | Template replace (Option A — new file's tabs overwrite) | P1 | B | shipped (untested on DEV) |
| XT-010 | Scenario upload: replace inputs file, validate I_-only | P1 | B | shipped (untested on DEV) |
| XT-011 | Scenario archive (non-destructive) | P1 | B | shipped |
| XT-012 | Run history per scenario | P1 | B | shipped |
| XT-013 | Drive integration for Inputs file (edit-in-Drive round-trip) | P1 | C | todo |
| XT-014 | Warm LibreOffice pool to cut calc latency | P2 | D | todo |
| XT-015 | Sensitivity sweep: materialize N scenarios from base + deltas | P2 | D | todo |

## Domain 20: Legacy TGV deprecation

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| DEL-001 | Delete legacy TGV code (models, routers, templates/template_groups UI) | P2 | Later | todo |
| DEL-002 | Firestore migration for existing TGV data (if we care to preserve) | P2 | Later | todo |
| DEL-003 | Remove `?legacy=1` nav flag once DEL-001 lands | P2 | Later | todo |

---



---

## Domain 1: Infrastructure & DevOps

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| INFRA-001 | Provision GCP project `masteko-fm` | P0 | 0 | todo |
| INFRA-002 | Firebase project + Auth (Google Sign-In + email) | P0 | 0 | todo |
| INFRA-003 | Cloud Run service (backend API) | P0 | 0 | todo |
| INFRA-004 | Firebase Hosting DEV site | P0 | 0 | todo |
| INFRA-005 | Firebase Hosting PROD site | P0 | 0 | todo |
| INFRA-006 | Firestore database (default) | P0 | 0 | todo |
| INFRA-007 | BigQuery dataset `masteko_fm` | P0 | 0 | todo |
| INFRA-008 | Artifact Registry repository | P0 | 0 | todo |
| INFRA-009 | Cloud Build trigger (push to main) | P0 | 0 | todo |
| INFRA-010 | Secret Manager secrets (Airtable key, etc.) | P0 | 0 | todo |
| INFRA-011 | Google Drive root folder `MastekoFM/` | P0 | 0 | todo |
| INFRA-012 | Makefile for local dev commands | P0 | 0 | todo |
| INFRA-013 | docker-compose.yml for local stack | P0 | 0 | todo |
| INFRA-014 | deploy-dev.sh script | P0 | 0 | todo |
| INFRA-015 | deploy-prod.sh script | P0 | 0 | todo |
| INFRA-016 | cloudbuild.yaml CI pipeline | P0 | 0 | todo |
| INFRA-017 | GitHub repo `mkoran/MastekoFM` initialized | P0 | 0 | todo |
| INFRA-018 | CLAUDE.md with all project rules | P0 | 0 | todo |
| INFRA-019 | Cloud Tasks queue for async jobs | P1 | 3 | todo |
| INFRA-020 | Monitoring + alerting (Cloud Monitoring) | P2 | 5 | todo |

## Domain 2: Authentication & Users

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| AUTH-001 | Firebase Auth setup (Google Sign-In) | P0 | 0 | todo |
| AUTH-002 | Auth middleware (bypass in DEV) | P0 | 0 | todo |
| AUTH-003 | User profile creation on first login | P0 | 1 | todo |
| AUTH-004 | User model (Firestore) | P0 | 1 | todo |
| AUTH-005 | Login/logout flow (frontend) | P0 | 1 | todo |
| AUTH-006 | Protected routes | P0 | 1 | todo |
| AUTH-007 | Organization model (multi-tenant) | P1 | 8 | todo |
| AUTH-008 | Role-based access (owner/editor/viewer) | P1 | 8 | todo |
| AUTH-009 | Invitation system | P1 | 8 | todo |
| AUTH-010 | Email/password auth option | P2 | 8 | todo |

## Domain 3: Projects

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| PROJ-001 | Project Firestore model | P0 | 1 | todo |
| PROJ-002 | Create project API | P0 | 1 | todo |
| PROJ-003 | List projects API | P0 | 1 | todo |
| PROJ-004 | Get project API | P0 | 1 | todo |
| PROJ-005 | Archive project API | P0 | 1 | todo |
| PROJ-006 | Drive folder auto-creation on project create | P0 | 1 | todo |
| PROJ-007 | Project dashboard page (frontend) | P0 | 1 | todo |
| PROJ-008 | Project detail/workspace page | P0 | 1 | todo |
| PROJ-009 | Project settings page | P1 | 4 | todo |
| PROJ-010 | Project collaborator management | P1 | 8 | todo |
| PROJ-011 | Project duplication (clone) | P2 | 7 | todo |

## Domain 4: Assumptions

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| ASMP-001 | Assumption Firestore model | P0 | 1 | todo |
| ASMP-002 | CRUD APIs for assumptions | P0 | 1 | todo |
| ASMP-003 | Type validation (number, %, currency, date, text, bool) | P0 | 1 | todo |
| ASMP-004 | Category grouping | P0 | 1 | todo |
| ASMP-005 | Assumptions table UI (editable data grid) | P0 | 1 | todo |
| ASMP-006 | Assumption history subcollection | P0 | 1 | todo |
| ASMP-007 | History entry on every value change | P0 | 1 | todo |
| ASMP-008 | Manual override (separate from source value) | P0 | 4 | todo |
| ASMP-009 | Override indicator in UI | P0 | 4 | todo |
| ASMP-010 | Assumption version history UI (timeline) | P1 | 4 | todo |
| ASMP-011 | Bulk import assumptions from CSV | P1 | 2 | todo |
| ASMP-012 | Assumption export to CSV | P2 | 4 | todo |
| ASMP-013 | Point-in-time reconstruction | P1 | 6 | todo |
| ASMP-014 | Assumption diff between two timestamps | P1 | 6 | todo |

## Domain 5: Data Sources

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| DS-001 | Data source Firestore model | P0 | 2 | todo |
| DS-002 | CSV connector (upload + parse) | P0 | 2 | todo |
| DS-003 | Excel connector (upload + parse) | P0 | 2 | todo |
| DS-004 | Airtable connector (API integration) | P0 | 2 | todo |
| DS-005 | Field discovery (list available fields from source) | P0 | 2 | todo |
| DS-006 | Field mapping UI (source field → assumption key) | P0 | 2 | todo |
| DS-007 | Manual sync trigger | P0 | 2 | todo |
| DS-008 | Sync status tracking | P0 | 2 | todo |
| DS-009 | Data source config UI | P0 | 2 | todo |
| DS-010 | Google Sheets connector | P1 | 8 | todo |
| DS-011 | Generic API connector (URL + auth) | P2 | 8 | todo |
| DS-012 | Scheduled sync (cron) | P2 | 8 | todo |
| DS-013 | Sync error handling + retry | P1 | 2 | todo |
| DS-014 | Type inference from source data | P1 | 2 | todo |

## Domain 6: Spreadsheet Templates

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| TPL-001 | Template Firestore model | P0 | 3 | todo |
| TPL-002 | Template upload API (.xlsx) | P0 | 3 | todo |
| TPL-003 | Named range discovery (inputs + outputs) | P0 | 3 | todo |
| TPL-004 | Template validation (named ranges exist, types correct) | P0 | 3 | todo |
| TPL-005 | Template versioning (changelog) | P0 | 3 | todo |
| TPL-006 | Template registry UI | P0 | 3 | todo |
| TPL-007 | Template preview (read-only grid) | P1 | 3 | todo |
| TPL-008 | Built-in starter templates (revenue, opex, financing) | P1 | 5 | todo |
| TPL-009 | Template marketplace (share across orgs) | P2 | 8+ | todo |

## Domain 7: Excel Engine

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| EXL-001 | openpyxl read/write named ranges | P0 | 3 | todo |
| EXL-002 | Inject assumption values into input cells | P0 | 3 | todo |
| EXL-003 | Formula evaluation (openpyxl formulas lib) | P0 | 3 | todo |
| EXL-004 | Extract output values from named ranges | P0 | 3 | todo |
| EXL-005 | LibreOffice headless fallback for complex formulas | P1 | 4 | todo |
| EXL-006 | Error handling (circular refs, #VALUE, #REF) | P0 | 3 | todo |
| EXL-007 | Calculation timing + logging to BigQuery | P1 | 4 | todo |
| EXL-008 | Support for XIRR, XNPV, other financial functions | P1 | 4 | todo |
| EXL-009 | Multi-sheet workbook support | P1 | 5 | todo |

## Domain 8: DAG (Spreadsheet Waterfall)

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| DAG-001 | DAG data model (nodes + edges in Firestore) | P0 | 3 | todo |
| DAG-002 | Cycle detection on edge creation | P0 | 3 | todo |
| DAG-003 | Topological sort | P0 | 3 | todo |
| DAG-004 | Cascade recalculation (execute DAG in order) | P0 | 3 | todo |
| DAG-005 | Output→input mapping (wire sheet outputs to downstream inputs) | P0 | 4 | todo |
| DAG-006 | Partial recalculation (only dirty nodes) | P1 | 4 | todo |
| DAG-007 | Error propagation (mark downstream as stale) | P0 | 4 | todo |
| DAG-008 | DAG editor UI (React Flow) | P0 | 3 | todo |
| DAG-009 | Node drag + position persistence | P0 | 3 | todo |
| DAG-010 | Edge drawing (connect output port → input port) | P0 | 3 | todo |
| DAG-011 | Node status indicators (idle/calculating/error/stale) | P0 | 4 | todo |
| DAG-012 | Manual recalculation trigger (per sheet or full DAG) | P0 | 4 | todo |
| DAG-013 | Async recalculation via Cloud Tasks | P1 | 5 | todo |

## Domain 9: Reports & PDF Generation

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| RPT-001 | Report Firestore model | P0 | 5 | todo |
| RPT-002 | Report template system (HTML/CSS) | P0 | 5 | todo |
| RPT-003 | Data binding (map sections to outputs/assumptions) | P0 | 5 | todo |
| RPT-004 | Chart generation (data → PNG) | P0 | 5 | todo |
| RPT-005 | PDF generation (WeasyPrint) | P0 | 5 | todo |
| RPT-006 | Store generated PDF in Google Drive | P0 | 5 | todo |
| RPT-007 | Report builder UI (template + bindings) | P0 | 5 | todo |
| RPT-008 | Report list + download UI | P0 | 5 | todo |
| RPT-009 | Branded cover pages | P1 | 5 | todo |
| RPT-010 | Table of contents generation | P1 | 5 | todo |
| RPT-011 | Investor package report template | P1 | 5 | todo |
| RPT-012 | Lender package report template | P1 | 5 | todo |
| RPT-013 | Custom report template upload | P2 | 7 | todo |

## Domain 10: Versioning & Scenarios

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| VER-001 | Project snapshot (freeze all values) | P0 | 6 | todo |
| VER-002 | Snapshot naming + metadata | P0 | 6 | todo |
| VER-003 | Snapshot list UI | P0 | 6 | todo |
| VER-004 | Snapshot comparison (side-by-side diff) | P1 | 6 | todo |
| VER-005 | Template version upgrade path | P1 | 6 | todo |
| VER-006 | Scenario manager (named override sets) | P1 | 7 | todo |
| VER-007 | Restore project to snapshot | P2 | 6 | todo |

## Domain 11: Analysis Tools

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| ANL-001 | Sensitivity analysis (one-variable) | P1 | 7 | todo |
| ANL-002 | Sensitivity chart (tornado diagram) | P1 | 7 | todo |
| ANL-003 | Two-variable data table | P2 | 7 | todo |
| ANL-004 | Dashboard KPI cards | P1 | 7 | todo |
| ANL-005 | Trend charts across scenarios | P1 | 7 | todo |
| ANL-006 | Full model export as single .xlsx workbook | P1 | 7 | todo |
| ANL-007 | Monte Carlo simulation | P2 | 8+ | todo |

## Domain 12: Frontend Shell

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| FE-001 | React + TypeScript + Vite + Tailwind setup | P0 | 0 | todo |
| FE-002 | Routing (React Router) | P0 | 0 | todo |
| FE-003 | Auth context + protected routes | P0 | 1 | todo |
| FE-004 | API client service (axios/fetch wrapper) | P0 | 1 | todo |
| FE-005 | Navigation layout (sidebar + header) | P0 | 1 | todo |
| FE-006 | Loading states + error boundaries | P0 | 1 | todo |
| FE-007 | Toast notifications | P1 | 2 | todo |
| FE-008 | Dark mode support | P2 | 7 | todo |

## Domain 13: Google Drive Integration

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| GD-001 | Drive API service (auth + CRUD) | P0 | 1 | todo |
| GD-002 | Folder creation per project | P0 | 1 | todo |
| GD-003 | File upload (xlsx, csv) | P0 | 2 | todo |
| GD-004 | File download | P0 | 2 | todo |
| GD-005 | File listing per project folder | P1 | 2 | todo |
| GD-006 | Permission management (share with collaborators) | P2 | 8 | todo |

## Domain 14: Observability & Logging

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| OBS-001 | Structured logging (Cloud Logging) | P0 | 0 | todo |
| OBS-002 | Health check endpoints (/health, /api/health/full) | P0 | 0 | todo |
| OBS-003 | Calculation audit log (BigQuery) | P1 | 4 | todo |
| OBS-004 | API request logging | P1 | 1 | todo |
| OBS-005 | Error tracking + alerting | P2 | 5 | todo |

## Domain 15: Checkout & Concurrency

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| CHK-001 | Checkout data model (project-level lock) | P0 | 1 | todo |
| CHK-002 | Checkout API (acquire / release / force-release) | P0 | 1 | todo |
| CHK-003 | 423 Locked response on all write endpoints when checked out | P0 | 1 | todo |
| CHK-004 | Auto-expiry of stale checkouts (default 2 hours) | P0 | 1 | todo |
| CHK-005 | Checkout banner UI (who has it, time remaining) | P0 | 1 | todo |
| CHK-006 | "Check out to edit" flow in frontend | P0 | 1 | todo |
| CHK-007 | Force-release by owner (UI + API) | P1 | 2 | todo |
| CHK-008 | Inactivity prompt (auto-checkin after idle period) | P1 | 4 | todo |
| CHK-009 | Per-sheet checkout (granular locking) | P2 | 8+ | todo |
| CHK-010 | Checkout audit trail (BigQuery) | P1 | 4 | todo |

## Domain 16: Spreadsheet Editing & Versioning

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| SED-001 | Download current .xlsx (with injected values) | P0 | 4 | todo |
| SED-002 | Re-upload modified .xlsx | P0 | 4 | todo |
| SED-003 | Named range re-discovery on upload | P0 | 4 | todo |
| SED-004 | Mapping change confirmation UI | P0 | 4 | todo |
| SED-005 | Sheet version history (per-sheet versions subcollection) | P0 | 4 | todo |
| SED-006 | Rollback to previous sheet version | P1 | 6 | todo |
| SED-007 | Sheet version diff (which named ranges changed) | P1 | 6 | todo |
| SED-008 | File size validation (10MB max) | P0 | 4 | todo |
| SED-009 | In-browser spreadsheet editor (Luckysheet / Handsontable) | P2 | 8+ | todo |

## Domain 17: Data Source Push-back

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| DS-015 | Airtable write-back connector | P2 | 8+ | todo |
| DS-016 | Configurable push-back mappings (outputs → Airtable fields) | P2 | 8+ | todo |
| DS-017 | Push-back trigger options (manual / on-recalc / scheduled) | P2 | 8+ | todo |
| DS-018 | Google Sheets write-back connector | P2 | 8+ | todo |

## Domain 18: Template Marketplace (future)

| ID | Item | Priority | Sprint | Status |
|---|---|---|---|---|
| MKT-001 | Publish template to marketplace | P2 | 8+ | todo |
| MKT-002 | Browse / search marketplace templates | P2 | 8+ | todo |
| MKT-003 | Import marketplace template into project | P2 | 8+ | todo |
| MKT-004 | Template ratings + usage stats | P2 | 8+ | todo |

---

## Backlog summary

| Domain | P0 | P1 | P2 | Total |
|---|---|---|---|---|
| Infrastructure | 17 | 1 | 1 | 20 |
| Auth & Users | 6 | 2 | 2 | 10 |
| Projects | 8 | 1 | 2 | 11 |
| Assumptions | 9 | 3 | 2 | 14 |
| Data Sources | 9 | 3 | 2 | 14 |
| Templates | 6 | 2 | 1 | 9 |
| Excel Engine | 5 | 3 | 0 | 9 |
| DAG | 9 | 3 | 0 | 13 |
| Reports | 8 | 4 | 1 | 13 |
| Versioning | 3 | 2 | 2 | 7 |
| Analysis | 0 | 4 | 3 | 7 |
| Frontend Shell | 6 | 1 | 1 | 8 |
| Google Drive | 4 | 1 | 1 | 6 |
| Observability | 2 | 2 | 1 | 5 |
| Checkout & Concurrency | 6 | 2 | 2 | 10 |
| Spreadsheet Editing | 5 | 2 | 2 | 9 |
| Data Source Push-back | 0 | 0 | 4 | 4 |
| Template Marketplace | 0 | 0 | 4 | 4 |
| **Total** | **103** | **36** | **31** | **173** |

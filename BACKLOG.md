# MastekoFM — Product Backlog

> Last updated: 2026-04-25
> Status: post-Sprint-UX-01 (bug bash + UX polish + smoke coverage shipped)
> Total roadmap: 8 sprints (A–H) + UX-01, then a longer Phase 3 backlog

---

## Sprint roadmap at a glance

| Sprint | Goal | Size | Dependencies |
|---|---|---|---|
| **A** | Hello World vertical slice — three-way composition runs end-to-end on tiny example | M (~5 days) | none — **✅ shipped v1.038** |
| **B** | Cleanup + Campus Adele migration — delete ~50% of legacy code, re-seed Campus Adele under new schema | M (~3-4 days) | A approved — **✅ shipped v2.001** |
| **A.5** | Tree Navigator — hierarchical browser (Project → Pack → Inputs/Outputs/Runs → cells) | M (~3-4 days) | B — **✅ shipped v2.003** |
| **INFRA-001** | CI/CD via GitHub Actions + Workload Identity Federation — auto-deploy on push, no re-auth | S (~1 day) | B — **✅ scaffolding shipped, awaits Marc setup** |
| **UX-01** | Bug bash (Create Pack 500, Calculate no-op) + UX polish (Projects/Models/Runs columns + filters + archive) + CI smoke gates for all gaps | L (~5-7 days) | A.5 — **✅ shipped v2.004** |
| **INFRA-002** | E2E smoke (seed + run + assert Sum=12) in CI — closes Sprint UX-01's "what the bash smoke can't catch" gap | XS (~2h) | UX-01 — **✅ shipped (script + workflow); activates fully when Marc shares Drive root with deployer SA** |
| **C** | Async runs via Cloud Tasks — POST returns 202; worker processes; UI polls. Sync-thread fallback when queue not configured | M (~4-5 days) | B — **✅ code shipped; activate per env via `./scripts/infra/setup_runs_queue.sh <env>`** |
| **D** | PDF OutputTemplates — WeasyPrint + first investor summary template for Campus Adele | S (~2-3 days) | B (can run parallel with C) |
| **E** | Multi-user permissions — Project members, owner/editor/viewer roles, Drive sharing automation | M (~4-5 days) | B |
| **F** | JSON AssumptionPacks + Airtable connector — schema declarations on Models, key→cell binding | L (~6-8 days) | B |
| **G** | Sensitivity sweeps + scenario comparison UI — batch-run, tornado/heatmap | M (~4-5 days) | C |
| **H** | Word + Google Docs OutputTemplates | M (~4-5 days) | D |
| Phase 3 | Templates marketplace, AI-assisted modeling, monitoring, observability | XL+ | A–H |

Detailed plans for each: [docs/sprints/](docs/sprints/).

---

## Status legend

- 🚧 **in progress**
- 🆗 **ready to start** (blocked by nothing, just need a dev)
- 🔒 **blocked** (waiting on a dependency)
- ✅ **shipped** (in DEV and verified)
- ❌ **not yet planned** (placeholder)

---

## Sprint A — Hello World vertical slice 🚧

> Goal: prove the three-way composition pattern works end-to-end on a tiny example. Marc reviews UI before committing to deletes/async.

Detailed plan: [docs/sprints/SPRINT_A_helloworld_slice.md](docs/sprints/SPRINT_A_helloworld_slice.md)

| ID | Story | Size | Status |
|---|---|---|---|
| A-001 | Create `seed/helloworld/` with 3 .xlsx files (Model, AssumptionPack, OutputTemplate) | XS | 🆗 |
| A-002 | Extend `excel_template_engine.classify_tabs()` to recognize `M_*` prefix | XS | 🆗 |
| A-003 | Add `OutputTemplate` Pydantic model + Firestore schema | S | 🆗 |
| A-004 | Add `Run` top-level Firestore model | S | 🆗 |
| A-005 | New service `run_validator.py` — three-way compatibility checker | S | 🆗 |
| A-006 | New service `run_executor.py` — two-stage Stage1+Stage2 pipeline | M | 🆗 |
| A-007 | Backend router `output_templates.py` — CRUD + upload | S | 🆗 |
| A-008 | Backend router `runs.py` — POST (sync for now), GET, list | S | 🆗 |
| A-009 | Backend route `seed.py` — `/api/seed/helloworld` uploads the 3 files + creates Project | S | 🆗 |
| A-010 | Frontend page `OutputTemplatesPage.tsx` — list + upload | S | 🆗 |
| A-011 | Frontend component `NewRunModal.tsx` — three-dropdown composer with compatibility filtering | M | 🆗 |
| A-012 | Frontend page `RunsPage.tsx` (basic) + `RunDetailPage.tsx` | S | 🆗 |
| A-013 | Backend tests: `test_run_validator.py`, `test_run_executor.py` (use Hello World fixtures) | S | 🆗 |
| A-014 | Layout: rename "Excel Templates" → "Models", add "Output Templates" + "Runs" nav items | XS | 🆗 |
| A-015 | Deploy + smoke test: hit `/api/seed/helloworld`, run end-to-end via UI, verify output `.xlsx` | XS | 🆗 |

**Definition of Done**: Marc opens https://dev-masteko-fm.web.app, navigates to Hello World project, picks Inputs+Model+OutputTemplate from three dropdowns, clicks Run, gets an `.xlsx` with `O_Report` showing Sum=12, Product=35, Total=47.

**Out of scope**:
- Deleting legacy code (Sprint B)
- Async execution (Sprint C)
- PDF/Word/GoogleDoc renderers (Sprints D/H)
- Multi-user permissions (Sprint E)
- JSON AssumptionPacks (Sprint F)

---

## Sprint B — Cleanup + Campus Adele migration

> Goal: delete the ~50% of code that's now dead. Re-seed Campus Adele under the new schema. Single source of truth.

Detailed plan: [docs/sprints/SPRINT_B_cleanup_and_migration.md](docs/sprints/SPRINT_B_cleanup_and_migration.md)

| ID | Story | Size | Status |
|---|---|---|---|
| B-001 | Delete legacy backend models: `template.py`, `template_group.py`, `assumption.py`, `datasource.py`, `dag.py`, legacy `project.py`, `report.py` | XS | 🔒 (waiting on A) |
| B-002 | Delete legacy routers: `templates.py`, `template_groups.py`, `assumptions.py`, legacy `projects.py`, `datasources.py`, `dag.py`, `spreadsheets.py`, `reports.py` | S | 🔒 |
| B-003 | Delete legacy services: `dag_executor.py`, datasource sync, assumption_engine | S | 🔒 |
| B-004 | Delete legacy frontend pages: `Dashboard.tsx`, `TemplatesPage.tsx`, `TemplateGroupsPage.tsx`, `ScenarioEditor.tsx`, `AssumptionsTable.tsx`, `DataSourceConfig.tsx`, `DAGEditor.tsx`, `ReportBuilder.tsx`, legacy `ProjectView.tsx` | S | 🔒 |
| B-005 | Remove `?legacy=1` flag and all branches of it from `Layout.tsx` | XS | 🔒 |
| B-006 | Delete legacy tests: TGV, datasource, dag, table_assumptions, checkout, etc. | XS | 🔒 |
| B-007 | Rename: `ExcelTemplate→Model`, `Scenario→AssumptionPack`, `ExcelProject→Project`, `excel_template_engine` stays (well-named), `scenario_store→pack_store` | S | 🔒 |
| B-008 | Firestore migration script: drop `dev_assumption_templates`, `dev_template_groups`, legacy `dev_projects/*/tgv`, `dev_projects/*/assumptions`, `dev_projects/*/datasources`, `dev_projects/*/spreadsheets` | S | 🔒 |
| B-009 | Delete the existing GCS-backed Optimistic + Base scenarios (old composition; no value preserved) | XS | 🔒 |
| B-010 | Build `seed/campus_adele/`: Model file, BaseCase AssumptionPack, default OutputTemplate (mirror of full workbook for now) | S | 🔒 |
| B-011 | `/api/seed/campus-adele` rewrites to upload 3 files + create Project under new schema | S | 🔒 |
| B-012 | Tag and bump VERSION to v2.000 (signals architectural pivot) | XS | 🔒 |
| B-013 | Deploy + smoke test: re-seed Campus Adele, run with Base AssumptionPack + Campus Adele Model + default OutputTemplate, verify output matches pre-cleanup | XS | 🔒 |
| B-014 | Update SESSION_HANDOFF.md, ARCHITECTURE.md "Last reviewed" markers, README.md if needed | XS | 🔒 |

**Definition of Done**: ~50% of source code deleted, no legacy references in nav or routers, Campus Adele runs successfully under new schema, all tests green, DEV deploys clean at v2.000.

**Out of scope**: Async (Sprint C). Sensitivity (Sprint G).

---

## Sprint C — Async runs via Cloud Tasks

> Goal: POST /api/runs returns 202 immediately, worker processes in background, frontend polls status. Foundation for sensitivity sweeps and 100+ concurrent.

Detailed plan: [docs/sprints/SPRINT_C_async_runs.md](docs/sprints/SPRINT_C_async_runs.md)

| ID | Story | Size | Status |
|---|---|---|---|
| C-001 | Create Cloud Tasks queue `mfm-runs-dev` and `mfm-runs-prod` (Terraform or one-shot script) | S | 🔒 |
| C-002 | Create second Cloud Run service `masteko-fm-worker-dev` from same image, different `--command` | S | 🔒 |
| C-003 | New router `internal_runs.py` — `/internal/tasks/run/{run_id}` endpoint, OIDC-only auth | S | 🔒 |
| C-004 | Wire `/api/runs` POST to enqueue Cloud Task; return 202 with `run_id` | S | 🔒 |
| C-005 | Worker handler: pull Run doc → run_executor → update Run status | S | 🔒 |
| C-006 | Cloud Tasks retry config: 3 attempts, exponential backoff | XS | 🔒 |
| C-007 | Frontend: polling component for Run status (Firestore onSnapshot or 2s poll) | S | 🔒 |
| C-008 | Frontend: "Cancel run" button (sets status=cancelled, worker checks before starting) | XS | 🔒 |
| C-009 | Frontend: "Retry" button on failed runs → POST /api/runs/{id}/retry | XS | 🔒 |
| C-010 | Cloud Run worker: separate IAM service account with Drive + Firestore + GCS perms | S | 🔒 |
| C-011 | Tests: mock Cloud Tasks, integration test for full enqueue→execute→status flow | M | 🔒 |
| C-012 | Update deploy-dev.sh to deploy both services (api + worker) from same image | S | 🔒 |
| C-013 | Smoke test: launch 5 concurrent runs, verify all complete | XS | 🔒 |

**Definition of Done**: Hello World run takes <500ms to POST and return; status updates from pending→running→completed within 5s; 5 concurrent runs all succeed; failed runs retry with backoff; UI shows live status.

---

## Sprint D — PDF OutputTemplates

> Goal: render OutputTemplates as PDF via WeasyPrint. First investor summary report for Campus Adele.

Detailed plan: [docs/sprints/SPRINT_D_pdf_outputs.md](docs/sprints/SPRINT_D_pdf_outputs.md)

| ID | Story | Size | Status |
|---|---|---|---|
| D-001 | Add WeasyPrint to backend requirements + Dockerfile | XS | 🔒 |
| D-002 | New `OutputTemplate.format` field — `"xlsx" \| "pdf"` (others later) | XS | 🔒 |
| D-003 | New `services/output_renderers/pdf_renderer.py` — HTML/CSS template + Model output bindings | M | 🔒 |
| D-004 | OutputTemplate stores HTML/CSS as a .zip in Drive (template + assets); validator checks for `{{ binding }}` placeholders | S | 🔒 |
| D-005 | run_executor branches on output_template.format → calls right renderer | S | 🔒 |
| D-006 | Build `seed/campus_adele/investor_summary/` — HTML+CSS template with charts + tables | M | 🔒 |
| D-007 | Frontend: OutputTemplate upload UI accepts .zip for PDF format | S | 🔒 |
| D-008 | Test: render Campus Adele PDF, verify file size + first-page render | S | 🔒 |

**Definition of Done**: User can upload an HTML/CSS PDF template, run with Campus Adele Model + Base AssumptionPack, download a real PDF investor summary.

---

## Sprint E — Multi-user permissions

> Goal: Project membership, role-based access, Drive folder sharing, last-admin protection.

Detailed plan: [docs/sprints/SPRINT_E_multi_user.md](docs/sprints/SPRINT_E_multi_user.md)

| ID | Story | Size | Status |
|---|---|---|---|
| E-001 | Project model gains `members: [{uid, role, email, added_at, added_by}]`; roles = owner/editor/viewer | S | 🔒 |
| E-002 | Auth middleware checks project membership for project-scoped endpoints | M | 🔒 |
| E-003 | Last-admin protection: cannot remove last owner from a project | XS | 🔒 |
| E-004 | Frontend: Project Settings tab — invite members by email, change role, remove | M | 🔒 |
| E-005 | Backend: when adding a member, share their Project's Drive folder with them via Drive API | S | 🔒 |
| E-006 | UI gating: viewers can see Runs but not start them; editors can; owners can manage members | S | 🔒 |
| E-007 | Audit log entry on every membership change | S | 🔒 |
| E-008 | Tests: each role × each protected operation | M | 🔒 |

**Definition of Done**: Marc invites a teammate, teammate signs in and sees only the projects they're a member of; viewer can't start a run; owner can remove the editor; cannot remove last owner.

---

## Sprint F — JSON AssumptionPacks + Airtable connector

> Goal: support non-Excel data sources. Model declares `input_schema` mapping JSON keys to cells. Airtable as the first connector.

Detailed plan: [docs/sprints/SPRINT_F_json_assumptions.md](docs/sprints/SPRINT_F_json_assumptions.md)

| ID | Story | Size | Status |
|---|---|---|---|
| F-001 | Model gains `input_schema: [{key, cell_ref, type, label}]` declarative binding | S | 🔒 |
| F-002 | New `AssumptionPack.format` field — `"xlsx" \| "json"` | XS | 🔒 |
| F-003 | JSON pack storage: stored as Firestore doc OR as `.json` file in Drive | S | 🔒 |
| F-004 | run_executor: when pack is JSON, iterate Model.input_schema, inject by cell_ref using openpyxl | M | 🔒 |
| F-005 | Frontend: per-Model "Input schema editor" — declare keys + cell refs | M | 🔒 |
| F-006 | Frontend: "New JSON pack" form — auto-generated from Model.input_schema | M | 🔒 |
| F-007 | Airtable connector service: pulls a base + table, snapshots into a versioned JSON pack | L | 🔒 |
| F-008 | Connector config UI: API key (Secret Manager), base ID, table, field mappings | M | 🔒 |
| F-009 | Manual sync button + scheduled sync (Cloud Scheduler) | M | 🔒 |
| F-010 | Tests: JSON pack injection into Hello World Model | S | 🔒 |
| F-011 | Tests: Airtable connector with mocked API | M | 🔒 |

**Definition of Done**: User defines input schema for Hello World Model; creates a JSON pack via form; runs and sees the same output as the .xlsx pack. Separately: configures an Airtable base; runs sync; resulting JSON pack feeds a Run.

---

## Sprint G — Sensitivity sweeps + comparison UI

> Goal: vary inputs systematically, run N variants, compare outputs.

Detailed plan: [docs/sprints/SPRINT_G_sensitivity_sweeps.md](docs/sprints/SPRINT_G_sensitivity_sweeps.md)

| ID | Story | Size | Status |
|---|---|---|---|
| G-001 | Backend: `Sweep` Firestore model — base_pack_id, variations: [{label, cell_ref, delta_type, delta}], output_keys | S | 🔒 |
| G-002 | Backend service: materialize a Sweep into N AssumptionPacks (programmatic openpyxl mutation) | M | 🔒 |
| G-003 | Backend: POST /api/sweeps creates Sweep + enqueues N Runs (uses Sprint C async) | S | 🔒 |
| G-004 | Backend: `/api/sweeps/{id}/results` aggregates output values across runs | S | 🔒 |
| G-005 | Frontend: Sweep builder — variation editor, output picker, launch | M | 🔒 |
| G-006 | Frontend: Tornado chart (Recharts) for one-variable sweep | S | 🔒 |
| G-007 | Frontend: Heatmap for two-variable sweep (later, optional) | M | 🔒 |
| G-008 | Frontend: Run comparison view — side-by-side cell diff between any 2-N runs | M | 🔒 |
| G-009 | Tests: sweep materialization with Hello World Model + 5 variations | S | 🔒 |

**Definition of Done**: User picks Campus Adele Base, declares "vary `Construction Duration` from 12 to 16 in steps of 1", clicks Sweep — 5 runs queued, completes in ~1 min, tornado chart shows IRR sensitivity to Construction Duration.

---

## Sprint H — Word + Google Docs OutputTemplates

> Goal: third and fourth output formats for completeness.

Detailed plan: [docs/sprints/SPRINT_H_word_googledocs.md](docs/sprints/SPRINT_H_word_googledocs.md)

| ID | Story | Size | Status |
|---|---|---|---|
| H-001 | Add `python-docx` to backend requirements | XS | 🔒 |
| H-002 | New `services/output_renderers/docx_renderer.py` — placeholder substitution into .docx template | M | 🔒 |
| H-003 | OutputTemplate.format = `"docx"` accepted; storage = Drive .docx | S | 🔒 |
| H-004 | Build `seed/campus_adele/lender_package.docx` template | S | 🔒 |
| H-005 | Add Google Docs API client (already enabled) | XS | 🔒 |
| H-006 | New `services/output_renderers/gdoc_renderer.py` — copy template Doc, fill placeholders via Docs API | M | 🔒 |
| H-007 | OutputTemplate.format = `"google_doc"`; storage = Drive Doc | S | 🔒 |
| H-008 | Frontend: format-aware upload UI per OutputTemplate type | S | 🔒 |
| H-009 | Tests: docx + gdoc renderer end-to-end with Hello World | S | 🔒 |

**Definition of Done**: User uploads a .docx OutputTemplate, runs Campus Adele, downloads a Word doc with substituted values. Same for a Google Doc template — output appears in user's Drive as a real Doc.

---

## Phase 3 — Long-term backlog

These are not yet sprint-planned. Each will be turned into a Sprint when we have user pull.

### Templates marketplace
- P3-001 Publish a Model or OutputTemplate to a workspace-wide library
- P3-002 Browse + clone marketplace templates into your project
- P3-003 Versioning across the marketplace (semver-style)
- P3-004 Ratings + usage metrics

### AI-assisted modeling
- P3-010 "What if I changed X by Y%" natural-language sensitivity via LLM → Sweep
- P3-011 Suggest input value ranges based on historical data
- P3-012 Auto-detect Model output dependencies on inputs (formula introspection)

### Observability + monitoring
- P3-020 Run duration histogram per Model, alert on regressions
- P3-021 Per-user usage metrics
- P3-022 Cost attribution: which Models/Templates burn the most LibreOffice CPU
- P3-023 Cloud Logging structured logs + log-based metrics
- P3-024 Error tracking integration (Sentry / Cloud Error Reporting)

### Categories + Dimensions (deferred per redesign decision)
- P3-030 First-class category metadata on AssumptionPack tabs (e.g., "Revenue", "Costs")
- P3-031 Dimensional rollups (project × scenario × time)
- P3-032 Cross-project queries: "all Runs of Construction-to-Perm v3 across all projects"

### Templates contract + advanced engine
- P3-040 Sheet diffing (xltrail-like, but free) using Drive revision IDs
- P3-041 Template-author lint: warn if I_ tabs contain cross-tab formula refs
- P3-042 Pivot table support inside calc tabs
- P3-043 Array formula support for I_/M_ injection

### Infrastructure hardening
- P3-050 Cloud Run min-instances tuning + warm pool for fast cold starts
- P3-051 Multi-region failover
- P3-052 Backup + restore for Firestore + Drive
- P3-053 Per-user rate limiting on /api/runs (prevent runaway sweeps)

---

## Backlog summary

| Sprint | P0 stories | P1 stories | Total |
|---|---|---|---|
| A | 15 | 0 | 15 |
| B | 14 | 0 | 14 |
| C | 13 | 0 | 13 |
| D | 8 | 0 | 8 |
| E | 8 | 0 | 8 |
| F | 11 | 0 | 11 |
| G | 9 | 0 | 9 |
| H | 9 | 0 | 9 |
| **Total** | **87** | **0** | **87** |
| Phase 3 | n/a | many | ~30 placeholders |

---

## Conventions

- Story IDs: `{SPRINT}-{NNN}` (e.g., `A-007`, `C-013`)
- Story sizes: `XS` (<2h), `S` (half day), `M` (1–2 days), `L` (3–4 days), `XL` (1 week+)
- An epic containing an XL story should be split before starting (per CLAUDE.md)
- Each sprint is on its own branch: `epic/sprint-{letter}-{name}` (e.g., `epic/sprint-a-helloworld`)
- Merge with `--no-ff` to preserve sprint boundaries

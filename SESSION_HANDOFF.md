# MastekoFM — Session Handoff

> Last updated: 2026-04-25
> Live DEV version: deploying v2.004 (Sprint UX-01)
> Current branch: `epic/sprint-b-cleanup` (carries Sprints B + INFRA-001 + A.5 + UX-01)

---

## What's been shipped (Sprints A → B → INFRA-001 → A.5 → UX-01)

### Sprint A — Hello World vertical slice (v1.029 → v1.038)
Three-way composition (`AssumptionPack × Model × OutputTemplate → Run`) working end-to-end on Hello World seed (Sum=12, Product=35, Total=47 verified live).

### Sprint B — Cleanup + Campus Adele migration (v2.000 → v2.002)
- ~50% of legacy code deleted (TGV / DAG / Datasource / per-project Spreadsheets / Reports stubs)
- Renamed: `ExcelTemplate→Model`, `ExcelProject→Project`, `Scenario→AssumptionPack`
- Firestore collections renamed: `excel_templates→models`, `excel_projects→projects`, `scenarios→assumption_packs` (subcollection)
- Project is now a thin org scope (`default_model_id` is optional)

### Sprint INFRA-001 — CI/CD scaffolding (file additions, no version bump)
- WIF setup script + 4 GitHub Actions workflows (CI, deploy-dev, deploy-prod, pr-preview)

### Sprint A.5 — Tree Navigator (v2.003)
- 4 backend tree endpoints + TreePage.tsx with 6 detail components

### Sprint UX-01 — Bug bash + UX polish + smoke coverage (v2.004)
**Bugs fixed:**
- **UX-01-01** Create AssumptionPack returned 500 in DEV — root cause: handler read legacy `template_id` field, post-Sprint-B is `default_model_id`. Fixed in `assumption_packs.py:_load_project_and_default_model`. Now returns 400 with helpful message when no default Model is bound, 201 on happy path. Frontend `ProjectView.tsx` re-typed against post-rename fields; "Default Model: (pinned to v)" display fixed; "Scenarios" terminology updated to "Assumption Packs"; GCS storage option dropped per CLAUDE.md doctrine.
- **UX-01-02** Calculate button no-op — same root cause; same fix path. Switched to `pack_store.load_model_bytes_compat()` so Drive-backed Models also work.

**Audit fields (UX-01-07):** `created_by_email`, `archived` boolean, `drive_url` / `drive_folder_url` derived fields added to all entity Responses + Summaries. Persisted in CREATE handlers via `current_user["email"]`.

**Archive (UX-01-08):** `archived: bool` added to Project, Model, AssumptionPack, OutputTemplate (independent of legacy `status` string; archive endpoints set both for back-compat). New endpoints: `POST /api/{models|output-templates|projects|assumption-packs}/{id}/archive` + `/unarchive`. List endpoints accept `?include_archived=true`; default hides archived.

**UI (UX-01-09 → 16):**
- ProjectsPage: rebuilt with columns Name · Created By · Created On · Default Model · Last Run · Drive URL · Runs · Status, per-column filters, Show-archived toggle, Archive/Unarchive inline action
- TreePage: archived projects already hidden (uses default `/api/projects` filter)
- ProjectView: Archive/Unarchive button + Drive-folder link in header
- RunsPage: Project + User (email) + Status filters with URL-as-state, sorted descending by `started_at`, denormalized names shown
- ModelsPage: drive_url column with "Open in Sheets" button (UX-01-15) + inline Drive file id editor (UX-01-16) + archive UI

**Smoke tests (UX-01-03 → 06):**
- pytest: +15 new tests across 3 new files (`test_assumption_packs_router.py`, `test_tree_router.py`, `test_seed_router.py`, `test_runs_router.py`). Total 81 (was 66). Both bug regressions are pinned by failing-without-fix tests.
- Post-deploy: `scripts/smoke/post_deploy_smoke.sh` consolidates health + auth surface + frontend HTML check + cache-header check. Replaces the inline curl in `deploy-dev.yml`, `deploy-prod.yml`, `deploy-dev.sh` (single source of truth).

---

## State of the codebase

| Metric | Value |
|---|---|
| Backend tests passing | **81/81** |
| ruff | clean |
| Frontend build | clean (~473 KB / ~123 KB gzipped, 68 modules) |
| Backend routers | 10 |
| Backend services | 7 |
| Frontend pages | 9 |
| Sprint UX-01 LOC delta | ~+1,500 added (audit fields, UX rewrites, smoke tests) |

---

## What's currently live on DEV

- https://dev-masteko-fm.web.app
- Cloud Run service: `masteko-fm-api-dev` (v2.004 once deploy completes)
- Firestore collections (active): `dev_projects`, `dev_models`, `dev_output_templates`, `dev_runs`, `dev_settings`, `dev_projects/*/assumption_packs`

---

## Outstanding from UX-01

| Item | Why deferred |
|---|---|
| Re-seed Hello World + Campus Adele on DEV after v2.004 deploy | Awaiting deploy + Marc's Google token |
| End-to-end Hello World assertion in CI (POST /api/seed/helloworld + POST /api/runs + assert Sum=12) | Requires service-account Drive token wiring; flagged as Sprint UX-02 candidate |
| Backfill `created_by_email` on existing Firestore docs | Cosmetic — old docs show "—" in the new "Created By" column |
| Merge `epic/sprint-b-cleanup` into `main` | Pending Marc's review of UX |

---

## What's next per BACKLOG

| Sprint | Goal | Status |
|---|---|---|
| Sprint C | Async runs via Cloud Tasks worker | ready to start |
| Sprint D | PDF OutputTemplates via WeasyPrint | ready to start (parallel to C) |
| Sprint E | Multi-user permissions + Drive folder sharing | ready to start (after B) |
| Sprint F | JSON AssumptionPacks + Airtable connector | ready to start |
| Sprint G | Sensitivity sweeps + comparison UI | needs C first |
| Sprint H | Word + Google Doc OutputTemplates | needs D first |

---

## Continuing from Cursor

```bash
cd "/Users/marckoran/My Drive (marc.koran@gmail.com)/MASTEKO/MSKCompanies/MarcKoran/CURSOR_AI/MastekoFM"
claude --continue
```

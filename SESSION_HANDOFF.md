# MastekoFM — Session Handoff

> Last updated: 2026-04-25
> Live DEV version: deploying v2.003 (Sprint A.5)
> Current branch: `epic/sprint-b-cleanup` (carries Sprint B + INFRA-001 + A.5)

---

## What's been shipped (Sprints A → B → INFRA-001 → A.5)

### Sprint A — Hello World vertical slice (v1.029 → v1.038)
Three-way composition (`AssumptionPack × Model × OutputTemplate → Run`) working end-to-end on Hello World seed (Sum=12, Product=35, Total=47 verified live).

### Sprint B — Cleanup + Campus Adele migration (v2.000 → v2.002)
- ~50% of legacy code deleted (TGV / DAG / Datasource / per-project Spreadsheets / Reports stubs)
- Renamed: `ExcelTemplate→Model`, `ExcelProject→Project`, `Scenario→AssumptionPack`
- Firestore collections renamed: `excel_templates→models`, `excel_projects→projects`, `scenarios→assumption_packs` (subcollection)
- Project is now a thin org scope (no required Model binding; `default_model_id` is optional UX convenience)
- API paths follow the rename
- `seed/campus_adele/` committed with `build_campus_adele_seed.py` + 3 .xlsx files
- `/api/seed/campus-adele` rewritten under new collections

### Sprint INFRA-001 — CI/CD scaffolding (no version bump, file additions)
- `scripts/infra/setup_github_wif.sh` one-shot setup (Marc runs once)
- `.github/workflows/ci.yml` (LibreOffice install added so engine tests run)
- `.github/workflows/deploy-dev.yml` (auto-deploys on push to `epic/**`)
- `.github/workflows/deploy-prod.yml` (manual approval via GitHub Environment)
- `.github/workflows/pr-preview.yml` (7-day Hosting preview per PR)
- `docs/sprints/SPRINT_INFRA_001_cicd.md` walkthrough

### Sprint A.5 — Tree Navigator (v2.003)
- Backend: `services/tree_browser.py` + 4 endpoints in `routers/tree.py`
- Frontend: `pages/TreePage.tsx` — left tree (lazy expand, filter, URL-as-state) + right detail pane
- 6 detail components: Project, Pack, Inputs (grouped by tab), Outputs (latest run), Runs, CellDetail (single-cell + history time-series)
- Layout: 🌳 Tree Navigator added at the top of the nav

---

## State of the codebase

| Metric | Value |
|---|---|
| Backend tests passing | **66/66** (down from 125 — legacy tests deleted in B) |
| ruff | clean |
| Frontend build | clean (~464 KB / ~121 KB gzipped, 68 modules) |
| Backend routers | 10 (assumption_packs, auth, health, models, output_templates, projects, runs, seed, settings, tree) |
| Backend models | 5 (model, project, assumption_pack, output_template, run, user) |
| Backend services | 7 (drive_service, excel_engine, excel_template_engine, pack_store, run_executor, run_validator, storage_service, tree_browser) |
| Frontend pages | 7 (Login, ProjectsPage, ProjectView, ModelsPage, OutputTemplatesPage, RunsPage, RunDetailPage, SettingsPage, TreePage) |
| Lines of code deleted in this session | ~4,000 |
| Lines of code added this session | ~3,500 (mostly tree + CI/CD + new entity routers) |

---

## What's currently live on DEV

- https://dev-masteko-fm.web.app
- Cloud Run service: `masteko-fm-api-dev` (v2.003 once deploy completes)
- Firestore collections (active): `dev_projects`, `dev_models`, `dev_output_templates`, `dev_runs`, `dev_settings`, `dev_projects/*/assumption_packs`
- Firestore collections (orphan from v1.x — re-seed or migrate):
  - `dev_excel_templates`, `dev_excel_projects`, `dev_excel_projects/*/scenarios`
  - `dev_assumption_templates`, `dev_template_groups` (TGV legacy)

To start clean post-deploy:
1. Sign in to dev-masteko-fm.web.app with Google
2. POST `/api/seed/helloworld` (with X-MFM-Drive-Token)
3. POST `/api/seed/campus-adele` (with X-MFM-Drive-Token)
4. Tree Navigator at /tree shows both projects, all their packs, inputs, outputs, runs

---

## What Marc needs to do to activate CI/CD (Sprint INFRA-001)

See [docs/sprints/SPRINT_INFRA_001_cicd.md](docs/sprints/SPRINT_INFRA_001_cicd.md).

Summary: ~15 minutes one-time:
1. `./scripts/infra/setup_github_wif.sh` (creates SA + WIF pool, prints the values)
2. Add 6 GitHub repository variables (paste values from script output)
3. Add 1 GitHub repository secret (`FIREBASE_SERVICE_ACCOUNT` JSON)
4. Create GitHub Environment "production" with required reviewers (yourself)
5. (Optional) Branch protection on main

After that: every push to `epic/*` auto-deploys to DEV. PROD deploys = button click + your approval.

---

## Outstanding from the just-finished sprints

| Item | Why deferred |
|---|---|
| Re-seed Hello World + Campus Adele on DEV after v2.003 deploy completes | Awaiting deploy + Marc's Google token |
| End-to-end smoke test of the Tree Navigator UI | Awaiting deploy + seed |
| Merge `epic/sprint-b-cleanup` into `main` | Pending Marc's review of UX |
| Old Firestore collections (`dev_excel_*`, `dev_template_groups`, `dev_assumption_templates`) | Orphaned; can be deleted via console or a one-shot script |

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

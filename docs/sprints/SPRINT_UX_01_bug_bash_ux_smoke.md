# Sprint UX-01 — Bug bash + UX polish + smoke coverage

> Status: ✅ shipped v2.004 (2026-04-25)
> Branch: `epic/sprint-b-cleanup` (continued)

## Goal

Fix the two production bugs Marc surfaced post-Sprint-A.5, polish the
Projects/Models/Runs pages with the columns + filters + archive flow he
asked for, and close the smoke-test gaps so the next regression is caught
in CI rather than in DEV.

## Stories

| ID | Story | Status |
|---|---|---|
| UX-01-01 | Diagnose & fix Create AssumptionPack 500 (root: legacy `template_id` field still read by `assumption_packs.py`) | ✅ |
| UX-01-02 | Diagnose & fix Calculate button no-op (same root cause) | ✅ |
| UX-01-03 | E2E /api/runs smoke test in pytest (mocked engine) | ✅ |
| UX-01-04 | Tree Navigator endpoint smoke tests (`tests/test_tree_router.py`) | ✅ |
| UX-01-05 | Frontend Hosting smoke (curl HTML, check no-cache header) | ✅ |
| UX-01-06 | Seed endpoints smoke (drive-token + auth gates) | ✅ |
| UX-01-07 | Audit fields (`created_by_email`, `triggered_by_email`, `archived`, `drive_url`, `drive_folder_url`) on all entities | ✅ |
| UX-01-08 | Archive endpoints + list filters (`?include_archived`) for Projects, Models, OutputTemplates, AssumptionPacks | ✅ |
| UX-01-09 | Projects list new columns (Created By, Created On, Default Model, Last Run, Drive URL, Runs link) | ✅ |
| UX-01-10 | Projects list per-column filters | ✅ |
| UX-01-11 | Projects list "Show archived" toggle (default off) | ✅ |
| UX-01-12 | Tree Navigator hides archived (uses default `/api/projects` filter) | ✅ |
| UX-01-13 | Project archive/unarchive buttons on ProjectsPage + ProjectView | ✅ |
| UX-01-14 | Run history filters (Project, User email, Status) + URL-as-state, sorted desc | ✅ |
| UX-01-15 | Models page shows drive_url + "Open in Sheets" button | ✅ |
| UX-01-16 | Models page edit Drive file id (PUT `/api/models/{id}` with `drive_file_id` triggers re-classify) | ✅ |
| UX-01-17 | Regression-test policy: bug fixes ship with a failing-then-passing test | ✅ (UX-01-01 + UX-01-02 each pinned) |

## Test count delta

- Before: **66/66**
- After: **81/81** (+5 assumption_packs regressions, +4 tree, +3 seed, +3 runs)

## Files changed

### Backend
- `backend/app/routers/assumption_packs.py` — bug fix + audit fields + archive endpoints
- `backend/app/routers/projects.py` — new ProjectSummary fields + run_count + last_run_at + unarchive endpoint
- `backend/app/routers/models.py` — drive_url + audit fields + archive/unarchive + drive_file_id swap
- `backend/app/routers/output_templates.py` — drive_url + audit fields + archive/unarchive
- `backend/app/routers/runs.py` — triggered_by_email + denormalized names + user filter on list
- `backend/app/models/{project,model,assumption_pack,output_template,run}.py` — additive fields

### Frontend
- `frontend/src/pages/ProjectsPage.tsx` — full rewrite (columns + filters + archive)
- `frontend/src/pages/ProjectView.tsx` — field renames + archive button + Drive folder link
- `frontend/src/pages/ModelsPage.tsx` — drive_url column + open-in-Sheets + inline edit
- `frontend/src/pages/RunsPage.tsx` — Project + User + Status filters with URL-as-state

### Tests + smoke
- `tests/test_assumption_packs_router.py` — 5 regression tests (UX-01-01 + UX-01-02)
- `tests/test_tree_router.py` — 4 endpoint tests (UX-01-04)
- `tests/test_seed_router.py` — 3 seed-gate tests (UX-01-06)
- `tests/test_runs_router.py` — 3 runs-router tests (UX-01-03 + UX-01-14)
- `scripts/smoke/post_deploy_smoke.sh` — single-source-of-truth post-deploy smoke
- `.github/workflows/deploy-dev.yml`, `.github/workflows/deploy-prod.yml`, `deploy-dev.sh` — call the smoke script

### Docs
- `SESSION_HANDOFF.md`, `BACKLOG.md`, this file

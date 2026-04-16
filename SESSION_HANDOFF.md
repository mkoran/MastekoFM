# MastekoFM — Session Handoff

> Last updated: 2026-04-16
> Version: 1.028 (pre-bump; deploy-dev.sh will bump on next DEV push)
> Branch: `epic/excel-template-mvp`

## What landed this session — Excel Template MVP

A new tab-prefix based architecture runs alongside the legacy TGV system:

- **Excel Template** = uploaded .xlsx whose tab prefixes declare the contract
  - `I_*` input tabs (humans edit these in Scenarios)
  - `O_*` output tabs (computed; not edited)
  - everything else = calc tabs
  - **Case-sensitive**: `i_Cap Table` is a calc tab, not an input
- **Excel Project** = one Template + many Scenarios
- **Scenario** = .xlsx with only the Template's `I_` tabs, stored in GCS
- **Calculate** = overlay Scenario's `I_` tabs onto Template, LibreOffice recalc, save full workbook

### Files added (all new)

Backend:
- `backend/app/models/excel_template.py`
- `backend/app/models/excel_project.py`
- `backend/app/models/scenario.py`
- `backend/app/services/storage_service.py`
- `backend/app/services/excel_template_engine.py`
- `backend/app/routers/excel_templates.py`
- `backend/app/routers/excel_projects.py`
- `backend/app/routers/scenarios.py`
- `backend/app/routers/excel_seed.py` (one-shot Campus Adele seed)

Tests (17 new, 84 total passing):
- `tests/test_excel_template_engine.py` (uses real Campus Adele fixture)
- `tests/test_excel_templates_router.py`
- `tests/test_excel_projects_router.py`
- `tests/fixtures/campus_adele.xlsx`

Frontend:
- `frontend/src/pages/ExcelTemplatesPage.tsx`
- `frontend/src/pages/ExcelProjectsPage.tsx`
- `frontend/src/pages/ExcelProjectView.tsx`
- Routes added in `App.tsx`; `Layout.tsx` shows new nav and hides TGV by default
  (use `?legacy=1` query to re-enable legacy TGV nav for reference)

### API endpoints (new)

```
POST    /api/excel-templates                       upload .xlsx, classify tabs
GET     /api/excel-templates                       list
GET     /api/excel-templates/{id}                  get detail
GET     /api/excel-templates/{id}/download         download URL
POST    /api/excel-templates/{id}/replace          upload new version (Option A)
PUT     /api/excel-templates/{id}                  update metadata
DELETE  /api/excel-templates/{id}                  delete

POST    /api/excel-projects                        create (needs template_id)
GET     /api/excel-projects                        list with scenario counts
GET     /api/excel-projects/{id}                   get
PUT     /api/excel-projects/{id}                   update
POST    /api/excel-projects/{id}/archive           archive

POST    /api/excel-projects/{pid}/scenarios                    create (optional clone_from_id)
GET     /api/excel-projects/{pid}/scenarios                    list
GET     /api/excel-projects/{pid}/scenarios/{sid}              get
PUT     /api/excel-projects/{pid}/scenarios/{sid}              update metadata
GET     /api/excel-projects/{pid}/scenarios/{sid}/download     inputs file URL
POST    /api/excel-projects/{pid}/scenarios/{sid}/upload       replace inputs file
POST    /api/excel-projects/{pid}/scenarios/{sid}/archive      archive
POST    /api/excel-projects/{pid}/scenarios/{sid}/calculate    run the pipeline
GET     /api/excel-projects/{pid}/scenarios/{sid}/runs         run history

POST    /api/excel-seed/campus-adele               one-shot Campus Adele seed (idempotent)
```

### Storage layout (GCS bucket masteko-fm-outputs)

```
excel_templates/<template_id>/v<N>_<filename>.xlsx
excel_projects/<project_code>/<scenario_code>/inputs_v<N>.xlsx
excel_projects/<project_code>/<scenario_code>/outputs/<timestamp>_<project>_<scenario>.xlsx
```

### Firestore collections (new)

```
{prefix}excel_templates/{template_id}
{prefix}excel_projects/{project_id}
{prefix}excel_projects/{project_id}/scenarios/{scenario_id}
{prefix}excel_projects/{project_id}/scenarios/{scenario_id}/runs/{run_id}
```

## Testing status

- Backend: **84/84 pytest passing** (67 legacy + 17 new), `ruff check` clean
- Frontend: `tsc --noEmit` clean, `npm run build` succeeds (481KB bundle, 126KB gzipped)
- Spike verified the architecture end-to-end on the real Campus Adele model:
  mutation of `Construction Duration` 13 → 14.3 propagated to **236 cells**
  of `O_Annual Summary` after LibreOffice recalc. See /tmp/mfm_spike_*.py.

## How to seed Campus Adele on DEV (after deploy)

```bash
# 1. DEV login in the browser at https://dev-masteko-fm.web.app
# 2. Grab your dev token or use: Authorization: Bearer dev-<email>
curl -X POST https://masteko-fm-api-dev-560873149926.northamerica-northeast1.run.app/api/excel-seed/campus-adele \
  -H "Authorization: Bearer dev-marc.koran@gmail.com" \
  -F "file=@Campus_Adele_Model_20260416_1410.xlsx"
# Returns: {template_id, project_id, scenario_base_id, scenario_optimistic_id}
# Then navigate to /excel-projects in the UI, click Campus Adele, hit Calculate.
```

## Known issues / not yet done

- Scenario files in Drive (`/api/excel-seed/campus-adele` writes to GCS only). Drive
  upload on Scenario create is the next step — requires Google OAuth token on the
  caller, per existing drive_service.py pattern.
- Template replace upload returns a diff report but UI doesn't surface it yet.
- Calculate is synchronous; for long recalcs we'll want Cloud Tasks. Current
  Campus Adele local recalc was ~3s; Cloud Run may be 10-15s with cold start.
- LibreOffice is installed in the Cloud Run Docker image per CLAUDE.md but
  the path check in `excel_engine._find_libreoffice()` only looks at `/usr/bin/*`
  and `shutil.which`. If Cloud Run uses `/usr/lib/libreoffice/program/soffice`,
  that still resolves via `which libreoffice` — should be fine.

## Decisions made this session

1. **Case-sensitive I_/O_ prefixes** (Campus Adele has `i_Cap Table` as a calc tab).
2. **GCS as primary storage** for MVP; Drive follows once the OAuth path is stable.
3. **Additive deploy** alongside TGV system (per CLAUDE.md additive-only rule).
   TGV nav hidden; backlog item DEL-001 tracks removing it later.
4. **Full workbook output** (not O_-only) — debuggable, shareable.
5. **Per-scenario inputs file**, not revisions on a single file.
6. **Template replace = Option A** — new upload's tabs overwrite the Template's tabs.
7. **Pull-on-demand** Calculate (no Drive watchers or auto-recalc).
8. **Archive**, not hard-delete, for Scenarios and Projects.

## Key file locations (for continuing)

- `backend/app/services/excel_template_engine.py` — the core engine (overlay + classify)
- `backend/app/routers/scenarios.py:234` — the Calculate endpoint
- `frontend/src/pages/ExcelProjectView.tsx` — the main user surface (scenario list + calc button)
- `tests/test_excel_template_engine.py` — use this as the regression suite when changing overlay logic
- `/tmp/mfm_spike_*.py` — the proving-ground spike scripts (don't delete; reference for debugging)

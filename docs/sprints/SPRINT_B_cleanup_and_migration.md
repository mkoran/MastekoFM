# Sprint B — Cleanup + Campus Adele migration

> Estimated: ~3-4 days
> Branch: `epic/sprint-b-cleanup` (off `main` after Sprint A merges)
> Goal: delete the ~50% of legacy code, re-seed Campus Adele under the new schema, tag v2.000.
> Blocked-by: Sprint A approved by Marc
> Blocks: Sprints C, D, E, F, G, H

---

## Why this sprint exists

Sprint A built the new world *alongside* the legacy code so Marc could review without commitment. This sprint deletes the legacy code now that the direction is approved. v2.000 marks the architectural pivot.

This is a **load-bearing cleanup**: nothing new is built; everything else is reorganized. Treat it as a single coherent commit per logical group.

---

## Goal & Definition of Done

- ~50% of source code deleted (legacy TGV, datasource, dag, spreadsheets, legacy projects)
- Renames complete: `ExcelTemplate→Model`, `ExcelProject→Project`, `Scenario→AssumptionPack`, `excel_template_engine` keeps name (well-named), `scenario_store→pack_store`
- Campus Adele re-seeded under new schema with: 1 Model, 1 AssumptionPack (BaseCase), 1 default OutputTemplate (mirror of full workbook for now)
- Old GCS-backed Optimistic + Base scenarios deleted (along with their old schema records)
- Firestore migration script run on DEV: drops `dev_assumption_templates`, `dev_template_groups`, etc.
- All tests green, ruff clean, npm build clean
- VERSION bumped to 2.000 (major bump signals architectural pivot)
- Deployed to DEV, smoke-tested
- All Markdown "Last reviewed" markers updated to today
- `?legacy=1` flag and all branches removed from frontend

---

## Out of scope

- Async runs (Sprint C)
- New output formats (Sprints D, H)
- Multi-user (Sprint E)
- JSON packs (Sprint F)
- Sweeps (Sprint G)

---

## Stories

### B-001 · Delete legacy backend models (XS)

```bash
rm backend/app/models/template.py
rm backend/app/models/template_group.py
rm backend/app/models/assumption.py
rm backend/app/models/datasource.py
rm backend/app/models/dag.py
rm backend/app/models/report.py
rm backend/app/models/project.py     # legacy version
```

Keep: `excel_template.py` (rename in B-007), `excel_project.py` (rename in B-007), `scenario.py` (rename in B-007), `user.py`.

---

### B-002 · Delete legacy backend routers (S)

```bash
rm backend/app/routers/templates.py
rm backend/app/routers/template_groups.py
rm backend/app/routers/assumptions.py
rm backend/app/routers/datasources.py
rm backend/app/routers/dag.py
rm backend/app/routers/spreadsheets.py
rm backend/app/routers/projects.py    # legacy
rm backend/app/routers/reports.py
rm backend/app/routers/excel_seed.py  # replaced by seed.py from Sprint A
```

Update `backend/app/main.py` — remove all corresponding `app.include_router(...)` lines.

Keep & rename: `excel_templates.py → models.py`, `excel_projects.py → projects.py`, `scenarios.py → assumption_packs.py`, `output_templates.py`, `runs.py`, `seed.py`, `auth.py`, `health.py`.

Note: there's still a `/api/settings` endpoint inside the old `template_groups.py`. Move it to a new `routers/settings.py` BEFORE deleting `template_groups.py`.

---

### B-003 · Delete legacy services (S)

```bash
rm backend/app/services/dag_executor.py
# datasource_sync, assumption_engine if they exist as separate files
```

Keep: `excel_template_engine.py`, `excel_engine.py`, `storage_service.py`, `drive_service.py`, `scenario_store.py` (rename to `pack_store.py`), `run_validator.py`, `run_executor.py`.

---

### B-004 · Delete legacy frontend pages (S)

```bash
rm frontend/src/pages/Dashboard.tsx     # legacy projects list
rm frontend/src/pages/TemplatesPage.tsx
rm frontend/src/pages/TemplateGroupsPage.tsx
rm frontend/src/pages/ScenarioEditor.tsx
rm frontend/src/pages/AssumptionsTable.tsx
rm frontend/src/pages/DataSourceConfig.tsx
rm frontend/src/pages/DAGEditor.tsx
rm frontend/src/pages/ReportBuilder.tsx
rm frontend/src/pages/ProjectView.tsx   # legacy version (the new one is ExcelProjectView, will be renamed)
rm frontend/src/pages/ExcelProjectsPage.tsx  # consolidated into ProjectsPage.tsx
rm frontend/src/pages/ExcelTemplatesPage.tsx # consolidated into ModelsPage.tsx
```

Update `App.tsx` — remove legacy routes, keep new route table:
- `/login`
- `/`
- `/projects`
- `/projects/:projectId`
- `/models`
- `/output-templates`
- `/runs`
- `/runs/:runId`
- `/settings`

---

### B-005 · Remove `?legacy=1` flag (XS)

**File**: `frontend/src/components/Layout.tsx`

Delete the `SHOW_LEGACY_TGV` constant and all branches that read it. The Layout becomes a clean single-purpose nav.

---

### B-006 · Delete legacy tests (XS)

```bash
rm tests/test_templates.py
rm tests/test_template_groups.py
rm tests/test_assumptions.py
rm tests/test_table_assumptions.py
rm tests/test_projects.py    # legacy
rm tests/test_datasources.py
rm tests/test_csv_connector.py
rm tests/test_excel_connector.py
rm tests/test_airtable_connector.py
rm tests/test_datasource_sync.py
rm tests/test_checkout.py
```

After deletes: ~70 tests remaining, all green.

---

### B-007 · Rename entities + collections (S)

This is the riskiest mechanical change. Do it in one atomic commit per file group.

| Old | New |
|---|---|
| `models/excel_template.py` | `models/model.py` |
| `models/excel_project.py` | `models/project.py` |
| `models/scenario.py` | `models/assumption_pack.py` |
| `routers/excel_templates.py` | `routers/models.py` |
| `routers/excel_projects.py` | `routers/projects.py` |
| `routers/scenarios.py` | `routers/assumption_packs.py` |
| `services/scenario_store.py` | `services/pack_store.py` |
| Firestore collection `excel_templates` | `models` |
| Firestore collection `excel_projects` | `projects` |
| Firestore subcollection `scenarios` | `assumption_packs` |
| Frontend `pages/ExcelTemplatesPage.tsx` | `pages/ModelsPage.tsx` |
| Frontend `pages/ExcelProjectsPage.tsx` | `pages/ProjectsPage.tsx` |
| Frontend `pages/ExcelProjectView.tsx` | `pages/ProjectView.tsx` |
| Frontend type `ExcelProject` | `Project` |
| Frontend type `ScenarioSummary` | `AssumptionPackSummary` |

API path changes:
- `/api/excel-templates` → `/api/models`
- `/api/excel-projects` → `/api/projects`
- `/api/excel-projects/{pid}/scenarios` → `/api/projects/{pid}/assumption-packs`

After this, do a `grep -r ExcelTemplate\\|ExcelProject\\|Scenario backend/ frontend/ tests/` to ensure nothing's stale.

---

### B-008 · Firestore cleanup script (S)

**File**: `scripts/migrate_to_v2.py`

```python
"""Drop legacy Firestore collections after Sprint B cleanup."""
from google.cloud import firestore

LEGACY_COLLECTIONS_TO_DROP = [
    "dev_assumption_templates",
    "dev_template_groups",
    # subcollections under dev_projects (legacy):
    # dev_projects/{*}/tgv
    # dev_projects/{*}/assumptions
    # dev_projects/{*}/datasources
    # dev_projects/{*}/spreadsheets
    # dev_projects/{*}/dag_edges
    # dev_excel_templates  → was renamed to dev_models in B-007 via copy+delete
    # dev_excel_projects   → was renamed to dev_projects in B-007 via copy+delete
]

def drop_collection(db, name):
    """Idempotent."""
    docs = list(db.collection(name).stream())
    print(f"{name}: {len(docs)} docs to delete")
    for doc in docs:
        # Recursively delete subcollections first
        for sub in doc.reference.collections():
            for sub_doc in sub.stream():
                sub_doc.reference.delete()
        doc.reference.delete()
    print(f"{name}: deleted")

# DRY-RUN by default; pass --execute to actually delete
```

Run on DEV first, verify, then PROD (later, when we have any).

---

### B-009 · Delete existing GCS-backed scenarios (XS)

The current Optimistic + Base + Drive Test scenarios from v1.x were against the old schema. After B-007 completes the rename, these docs will be in `dev_projects/{campus_adele_id}/assumption_packs/` but with old field shapes.

Easiest path: just delete them via the script. They'll be re-created in B-011.

```python
# In migrate_to_v2.py
old_proj_id = "WILJkqx44RYhtberWGSV"  # the v1 Campus Adele
db.collection("dev_projects").document(old_proj_id).delete()
# Re-create cleanly in B-011
```

---

### B-010 · Build `seed/campus_adele/` (S)

**Files**: `seed/campus_adele/`
- `campus_adele_model.xlsx` — the existing 15-tab construction-to-perm Model. Strip the existing `I_*` tabs back to a "template" state (keep the structure but don't pre-populate with Base values). Or: keep as-is and use it as the canonical Model.
- `campus_adele_base_pack.xlsx` — only the `I_*` tabs with Base Case values
- `campus_adele_summary.xlsx` — first OutputTemplate. Minimal: an `M_Annual Summary` tab + an `O_Report` tab that surfaces a few key cells. (More complex investor-summary template comes in Sprint D as PDF.)
- `seed/campus_adele/README.md`

Get the existing `Campus_Adele_Model_20260416_1410.xlsx` from `tests/fixtures/campus_adele.xlsx` as the starting point.

---

### B-011 · `/api/seed/campus-adele` rewrite (S)

Replaces the v1 endpoint. New behavior:
1. Idempotent by `code_name`
2. Uploads campus_adele_model.xlsx → Model
3. Uploads campus_adele_base_pack.xlsx → AssumptionPack (under Project)
4. Uploads campus_adele_summary.xlsx → OutputTemplate
5. Creates Project "Campus Adele"

Lives in `backend/app/routers/seed.py`.

---

### B-012 · VERSION bump to 2.000 (XS)

**File**: `VERSION`

```
2.000
```

The major version bump signals: architectural pivot, breaking schema changes, all-new entity names. Future deploys bump the .NNN counter.

`deploy-dev.sh` should accept the format unchanged.

---

### B-013 · Deploy + smoke test (XS)

1. Run `scripts/migrate_to_v2.py --execute` against DEV Firestore
2. `./deploy-dev.sh` → builds + deploys, version 2.001
3. Health check 200
4. Hit `/api/seed/campus-adele` and `/api/seed/helloworld`
5. Open UI, verify:
   - Projects list shows "Hello World" + "Campus Adele"
   - Models list shows both Models
   - Output Templates list shows both
   - Click "+ New Run" on Campus Adele → pick BaseCase + Campus Adele Model + Summary OutputTemplate → Run
   - Verify output downloads, opens in Excel, looks reasonable
6. Repeat for Hello World — Sum=12, Product=35, Total=47

---

### B-014 · Doc freshness pass (XS)

Update "Last reviewed" markers to today on:
- README.md
- ARCHITECTURE.md
- BACKLOG.md (mark Sprint A ✅, Sprint B 🚧→✅)
- SESSION_HANDOFF.md (write up new state)
- CLAUDE.md (mark redesign-related sections current)

---

## API path changes summary (BREAKING)

| Old | New | Why |
|---|---|---|
| `/api/excel-templates` | `/api/models` | Rename |
| `/api/excel-projects` | `/api/projects` | Rename |
| `/api/excel-projects/{p}/scenarios` | `/api/projects/{p}/assumption-packs` | Rename |
| `/api/excel-projects/{p}/scenarios/{s}/calculate` | `POST /api/runs` | Different shape — composition body |
| `/api/projects/{p}/...` (legacy TGV) | DELETED | Legacy |
| `/api/template-groups` | DELETED | Legacy TGV |
| `/api/datasources/...` | DELETED | Legacy |
| `/api/dag/...` | DELETED | Legacy |

This is a major version bump (v2.000) — clients must update.

---

## Firestore migration

DRY RUN first. Verify the count of docs to delete matches expectations. Then `--execute`.

```
dev_assumption_templates       (delete)
dev_template_groups            (delete)
dev_projects/*/tgv             (delete subcollection)
dev_projects/*/assumptions     (delete subcollection)
dev_projects/*/datasources     (delete subcollection)
dev_projects/*/spreadsheets    (delete subcollection)
dev_projects/*/dag_edges       (delete subcollection)

dev_excel_templates            (rename to dev_models via copy+delete)
dev_excel_projects             (rename to dev_projects, replacing legacy)
dev_excel_projects/*/scenarios (rename to assumption_packs)
```

---

## Risks

| Risk | Mitigation |
|---|---|
| Renames miss a reference, cause runtime errors | Comprehensive grep + test suite + DEV smoke test before declaring done |
| Firestore migration corrupts data | DRY RUN first; backup with Firestore export before --execute |
| Drive folder structure stays from v1 (campus_adele/inputs/inputs_v1.xlsx) | Leave as-is; new code writes to new paths; old paths can be cleaned manually later |
| Marc wants to keep something we're deleting | Freeze plan with Marc before starting; show explicit delete list |
| User can't sign in because of stale token | Already mitigated by no-cache index.html (v1.034) |

# Drive hierarchy + versioning — final decisions (locked in)

> Companion to `PROPOSAL_drive_hierarchy_and_versioning.md`. Captures Marc's
> decisions from 2026-04-27 and the standards that flow from them.

## Decisions

| # | Decision | Marc's call |
|---|---|---|
| 1 | Nest projects under `Projects/` | ✅ yes |
| 2 | Per-run folder name `{YYYYMMDD-HHMMSS}_{pack}_{tpl}/` | ✅ yes |
| 3 | Versioning approach | ✅ yes — **but encode version in filename**, not via Drive's native revision history |
| 4 | Migrate old runs vs leave legacy | ✅ leave legacy |
| 5 | Models keep GCS dual-support? | ❌ no — **drop GCS entirely**, put a new Hello World in place |
| 6 | "Calculations folder" on Models page | ✅ query view (no duplicate storage) |
| 7 | Workspaces above Projects | ✅ **NEW** — implement now, permissions later |

## Filename encoding standard

Every artifact filename includes its version. Drive sees uniquely named files;
sorting by name = sorting by version = sorting by upload time.

### Format
```
{entity_code}_v{NNN}[_{role}].{ext}
```

Where:
- `entity_code` — the slug, e.g. `helloworld_inputs`, `campus_adele_model`
- `NNN` — 3-digit zero-padded version (`001`, `002`, …, `999`). At v1000 we
  switch to 4 digits — fine because it still sorts lexically.
- `role` — optional, only used for output artifacts within a Run folder where
  multiple files coexist for the same version (e.g., `_xlsx`, `_pdf`)
- `ext` — `xlsx`, `pdf`, `docx`, `txt`

### Examples

```
Models/helloworld_model/
  helloworld_model_v001.xlsx
  helloworld_model_v002.xlsx
  helloworld_model_v003.xlsx          ← canonical "current" = highest version

OutputTemplates/helloworld_report/
  helloworld_report_v001.xlsx

Projects/helloworld/AssumptionPacks/helloworld_inputs/
  helloworld_inputs_v001.xlsx
  helloworld_inputs_v002.xlsx
  helloworld_inputs_v003.xlsx

Projects/helloworld/Runs/20260427-180000_helloworld_inputs_helloworld_report/
  helloworld_inputs_helloworld_report_v001.xlsx       ← the calculated output
  helloworld_inputs_helloworld_report_v001.pdf        ← future (Sprint D)
  run-log_v001.txt                                    ← warnings + timing
```

### Rationale

- **Self-describing**: looking at a filename in Drive UI tells you the entity, version, and (with the run-folder timestamp) when. No metadata lookup.
- **Sortable**: lexical sort = version sort = chronological sort.
- **Drive-API-friendly**: uniqueness is enforced at write time (no naming collisions).
- **Doesn't fight Drive's revision history**: each version is a distinct file, so users in Drive UI see all versions side-by-side. (Drive's revision history still works on each file individually, but isn't the source of truth.)

### Why not `{code}_v1_{timestamp}.xlsx`?

Adding the timestamp to the FILENAME would be redundant — version bumps with time, so version order = time order. Timestamps go in the per-run FOLDER name (which contains output files for one run), not in individual filenames. Within an entity's own folder (e.g., `Models/{code}/`), version is enough.

### Code utility

A single helper `versioned_filename(code, version, ext)` is the only correct
way to build these names. Lives in `backend/app/services/drive_service.py`:

```python
def versioned_filename(code: str, version: int, ext: str = "xlsx") -> str:
    return f"{code}_v{version:03d}.{ext}"
```

Routers + workers must use this — never hand-format.

---

## Workspaces

### Concept
A **Workspace** sits above Projects. It's the unit a person belongs to and
(later) the unit of permission. A user can be a member of multiple workspaces.

```
Workspace
├── Models                 ← workspace-scoped (not global)
├── OutputTemplates        ← workspace-scoped
└── Projects
    ├── AssumptionPacks
    └── Runs
```

### Drive layout with workspaces
```
{drive_root_folder_id}/
└── MastekoFM/
    └── Workspaces/
        └── {workspace_code}/                  ← per-workspace
            ├── Models/
            │   └── {model_code}/
            │       ├── {model_code}_v001.xlsx
            │       └── {model_code}_v002.xlsx
            ├── OutputTemplates/
            │   └── {tpl_code}/
            │       └── {tpl_code}_v001.xlsx
            └── Projects/
                └── {project_code}/
                    ├── AssumptionPacks/
                    │   └── {pack_code}/
                    │       ├── {pack_code}_v001.xlsx
                    │       └── {pack_code}_v002.xlsx
                    └── Runs/
                        └── 20260427-180000_{pack}_{tpl}/
                            ├── {pack}_{tpl}_v001.xlsx
                            └── run-log_v001.txt
```

### Firestore schema

New collection: `dev_workspaces` / `prod_workspaces`.

```python
class Workspace:
    id: str                        # Firestore doc id
    name: str                      # human display
    code_name: str                 # slug for Drive folder
    description: str
    members: list[str]             # user uids — permissions later
    drive_folder_id: str           # the Drive folder for this workspace
    archived: bool = False
    created_by: str
    created_by_email: str | None
    created_at: datetime
    updated_at: datetime
```

`Project` doc gets one new field:
```diff
+ workspace_id: str                # which workspace this project belongs to
```

### Default workspace
On first sign-in, auto-create a workspace named "Personal" (`code_name="personal"`)
with the user as the sole member. New projects default to the user's first
workspace if not explicitly specified.

### Permissions (deferred)
Members list is recorded today but NOT enforced. Any authenticated user can
read/write any workspace. We'll add role-based checks (owner/editor/viewer)
in a separate sprint when permissions become a real need.

---

## What changes (concrete summary)

| Area | Change |
|---|---|
| **New entity** | `Workspace` — Pydantic model, router, Firestore collection, frontend page |
| **Project** | Gains `workspace_id` field; routers filter projects by workspace |
| **Drive layout** | Workspaces/{ws}/{Models,OutputTemplates,Projects/...} |
| **Filenames** | `{code}_v{NNN}.{ext}` everywhere — new helper `versioned_filename()` |
| **Models** | Move from GCS to Drive. Each Model has its own Drive folder. |
| **Run outputs** | Move from flat GCS files to per-run Drive folders containing versioned artifacts |
| **GCS** | `services/storage_service.py` deleted (or stubbed). `GCSStore` deleted. `MFM-OUTPUTS` bucket no longer used at runtime. |
| **Hello World** | New seed under new structure. Old Hello World ignored or wiped. |
| **Front end** | Workspace switcher (top of nav), workspace settings page, Drive folder URLs on Models / Runs / Project pages |

---

## Migration / cleanup plan

Marc said "I would not care if you broke hello world". So:

1. **Code change ships first** — new architecture, no GCS reads
2. **Wipe DEV Firestore docs** for old hello world (project, model, pack, template, runs)
3. **Re-seed Hello World** under new layout via the updated `/api/seed/helloworld` endpoint
4. **PROD**: same recipe whenever Marc decides to seed PROD

Old runs in Firestore that have `storage_path` (GCS) instead of Drive output folders → mark them visually in the UI as "legacy run" and disable the download link (or keep the GCS link if the bucket still exists; we won't be writing to it anymore but reads can stay until the bucket is decommissioned).

Old packs, models, OutputTemplates → all wiped + re-created.

---

## Sprint G1 scope (what I'm building right now)

1. Filename encoding helper
2. Workspace entity (model + router + Firestore collection)
3. Default workspace auto-create on user creation
4. Drive folder helpers (`ensure_workspace_folders`, `ensure_pack_folder`, `ensure_run_folder`)
5. Models upload → Drive (drop GCS)
6. Runs output → Drive per-run folder (drop GCS)
7. Pack uploads use new versioned filename + new folder structure
8. OutputTemplate uploads use new structure
9. Drop `storage_service.py` GCS code + `GCSStore`
10. Update `seed/helloworld/` files + `/api/seed/helloworld` endpoint to use new architecture
11. Tests
12. Deploy DEV via GH Actions

## Sprint G2 scope (next)

13. Workspace UI (switcher + settings page)
14. Models page Drive-folder column + "Calculations" query view
15. Model detail page (new)
16. RunDetail folder URL + artifacts list
17. Pack revision history panel + endpoints

---

## What stays the same

- Three-way composition (Project + Model + Pack + OutputTemplate → Run)
- Engine (LibreOffice + openpyxl, two-stage pipeline)
- Cloud Tasks async workers
- KMS encryption of Drive tokens
- The CI E2E smoke gate (will pass after migration)

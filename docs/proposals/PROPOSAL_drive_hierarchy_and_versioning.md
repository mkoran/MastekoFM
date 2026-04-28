# Proposal — Drive folder hierarchy + version history (planning doc)

> Status: draft for Marc's review. Implementation kicks off after approval.
> Affects: Models page · AssumptionPack list · RunDetail · backend Drive layout
> Estimated as 2 sprints (G1 = data model + folders, G2 = UX surfaces)

## Why now

Several user-facing asks Marc surfaced today:

1. "When I look at a Model, I want to see its **Drive folder** (where the file lives) and its **outputs/calculations folder** (where every Run that used this Model dumps its artifacts)."
2. "I want **version history** for AssumptionPack inputs — every upload tracked, browsable, openable."
3. "Outputs are no longer single files — `.xlsx` today, `.pdf` and `.docx` and Google Doc soon. The 'output' is a **folder**, not a file. Each Run gets its own folder."
4. "Tell me **what the Drive structure looks like** so I can navigate my files in Drive directly, not just via the app."

The current structure (Sprint B → today) is functional but flat. It doesn't carry version info in folder layout, doesn't have per-run folders, and Models aren't in Drive at all.

---

## Current structure (what exists today)

```
{drive_root_folder_id}/                        ← e.g. "Marc's MastekoFM root"
└── MastekoFM/                                 ← namespace (created lazily)
    ├── OutputTemplates/                       ← all output-templates flat here
    │   └── helloworld_report.xlsx             ← Drive revisions track versions
    │
    └── {project_code}/                        ← per-project folder
        ├── Inputs/
        │   └── {pack_code}.xlsx               ← ONE file per pack; Drive revisions = versions
        │
        └── Outputs/
            └── {ts}_{proj}_{pack}_{tpl}.xlsx  ← one flat file per run
```

**Models are not in Drive.** They live in GCS at `gs://masteko-fm-outputs/models/{id}/v1_{filename}.xlsx`. The Models page can't show a Drive URL because there isn't one.

**Versioning is implicit.** Every `drive.files.update` (re-upload of a pack) preserves the prior revision via Drive's `revisions` API, but those revisions are only browsable from Drive's "File → Version history" menu — they don't appear as separate files.

**Outputs are flat files.** A run produces one `.xlsx`, dropped into the project's `Outputs/`. No room for additional artifacts (`.pdf`, `.docx`, log files, screenshots).

---

## Proposed structure

```
{drive_root_folder_id}/
└── MastekoFM/
    │
    ├── Models/                                ← NEW — Models live in Drive too
    │   └── {model_code}/                      ← one folder per Model
    │       ├── {model_code}.xlsx              ← canonical current version
    │       │                                  (Drive revisions = past versions)
    │       └── README.txt                     ← optional notes (auto-generated)
    │
    ├── OutputTemplates/                       ← unchanged
    │   └── {tpl_code}/                        ← NEW — wrap each in a folder
    │       └── {tpl_code}.xlsx
    │
    └── Projects/                              ← NEW level — keeps top of MastekoFM clean
        │
        └── {project_code}/                    ← per-project (today flat under MastekoFM/)
            │
            ├── AssumptionPacks/               ← renamed Inputs/
            │   └── {pack_code}/               ← one folder per pack
            │       └── {pack_code}.xlsx       ← canonical current version
            │       (Drive revisions = past versions; UI exposes them)
            │
            └── Runs/                          ← renamed Outputs/
                └── {YYYYMMDD-HHMMSS}_{pack_code}_{tpl_code}/   ← one folder per run
                    ├── output.xlsx            ← always present today
                    ├── output.pdf             ← future (Sprint D)
                    ├── output.docx            ← future (Sprint H)
                    └── run-log.txt            ← optional warnings + timing
```

**Key changes:**

| Change | Why |
|---|---|
| Move Models into Drive | Marc's #1 ask. Same pattern as packs/templates. Frees us from the GCS-vs-Drive split. |
| `Models/{code}/` folder per Model | Gives the Models page a Drive URL to surface. Drive revisions still hold version history. |
| `OutputTemplates/{code}/` folder per Template | Symmetry. Lets templates own auxiliary files later (preview thumbnails, schema docs). |
| `Projects/` namespace level | Keeps `MastekoFM/` tidy — just three things at the top: Models, OutputTemplates, Projects. |
| `AssumptionPacks/{code}/` folder per pack | Future-proofs: a pack can carry attachments, source-data dumps, etc. |
| `Runs/{ts}_{p}_{t}/` folder per run | The big one. Each Run is a folder containing all artifacts (xlsx, pdf, docx, log). Solves "outputs are folders not files". |

**What stays the same:**

- Drive's revision history is still the source of truth for past versions of any one file. We don't create `v1/` `v2/` subfolders — that fights Drive's natural model and clutters the UI.
- `update_file_content` (Sprint B) still preserves Sheets edit URLs across re-uploads.
- The deployer SA's Editor access on the root cascades to all of this.

---

## What changes per page

### Models page

Today: shows tab counts, version, "Open in Sheets" (which uses GCS public URL).

Proposed:

```
| Name        | Code            | v   | I_  | O_  | calc | Drive folder      | URL          | Created By     | Updated      | Status |
|-------------|-----------------|-----|-----|-----|------|-------------------|--------------|----------------|--------------|--------|
| Hello World | helloworld_model| v3  | 1   | 1   | 1    | 📁 Models/helloworld_model | Open in Sheets | marc@... | 2026-04-27 | active |
```

Two new columns:
- **Drive folder** → click goes to `https://drive.google.com/drive/folders/{model_folder_id}` — the folder containing the .xlsx
- **URL** → "Open in Sheets" opens the file itself (already exists)

Plus on the **Model detail page** (new, currently a Model has no detail page):
- The folder URL prominently
- A "Calculations folder" section that lists ALL Runs that used this Model — with each run linked to its own `Runs/{ts}_*/` folder. (This isn't a single Drive folder; it's a query result. Still fits the "where calculations live" mental model.)
- Version history (revisions list from Drive, with download/preview buttons)

### Models page — "+ New Model" flow

Today: upload an .xlsx, it goes to GCS.

Proposed:
1. User clicks "+ New Model"
2. Backend creates `MastekoFM/Models/{model_code}/` (or its slug)
3. Upload the .xlsx into that folder
4. Persist the folder id + file id in Firestore on the Model doc
5. Models page shows the new row with the Drive folder link

### AssumptionPack list (Tree Navigator + ProjectView)

Today: shows pack name + current version.

Proposed: each pack row shows
- Current version
- "📜 History" button → opens a panel showing all Drive revisions:
  - timestamp, who uploaded it, file size
  - "Open this version" button → fetches the historic revision via Drive API (`revisions.get(media)`)
  - "Make current" button → restore that revision to the head (keeps history intact)

Backend change: new endpoint
```
GET  /api/projects/{p}/assumption-packs/{id}/revisions
POST /api/projects/{p}/assumption-packs/{id}/revisions/{rev_id}/restore
```

### Runs page + RunDetail

Today: each run has `output_download_url` (single .xlsx).

Proposed:
- New field `output_folder_id` on Run docs (Drive folder for that run's artifacts)
- New field `output_artifacts` — list of `{format, drive_file_id, download_url}`
- RunDetail shows the **Drive folder URL** prominently AND a list of all artifacts (xlsx today, pdf/docx tomorrow)
- Runs page table gets a "📁 Folder" column

Backwards compat: the old `output_download_url` (single GCS link) keeps working for old runs.

### Project detail (the existing page)

Today: shows pack list + "+ New Run" button.

Proposed: add a header row with "📁 Drive folder" → `Projects/{project_code}/`. (The folder structure already exists; just surface the link.)

---

## Data model changes

All additive (no migration breaks). Old docs continue to work.

### Model doc
```diff
+  drive_folder_id: str | None     # the per-Model folder
+  drive_file_id: str | None       # already exists, often null today
+  drive_folder_url: str | None    # derived helper (could compute on read)
   storage_path: str | None        # GCS — keep for back-compat; new Models won't use
```

### AssumptionPack doc
```diff
+  drive_folder_id: str | None     # NEW — the per-pack folder
   drive_file_id: str | None       # the .xlsx inside the folder
```

### Run doc
```diff
+  output_folder_id: str | None              # the per-run folder in Drive
+  output_artifacts: list[ArtifactRef]       # one entry per format
   output_download_url: str | None           # legacy single URL — keep
   output_drive_file_id: str | None          # legacy — keep
```

Where `ArtifactRef = {format: "xlsx"|"pdf"|"docx", drive_file_id, download_url, size_bytes}`.

### OutputTemplate doc
```diff
+  drive_folder_id: str | None     # the per-template folder (was using OutputTemplates/ flat)
```

---

## Migration story

Existing data on DEV + PROD:
- 6 projects, ~12 packs, 1-2 models, 1 OutputTemplate, ~20 runs

Migration script `scripts/migrate/move_to_hierarchy_v2.py` (one-shot, idempotent):
1. For each Model: create `Models/{code}/` folder, move the existing GCS-or-Drive file into it (or re-upload from GCS), record `drive_folder_id`
2. For each OutputTemplate: create `OutputTemplates/{code}/`, move file in, record id
3. For each Project: create `Projects/{project_code}/AssumptionPacks/{pack}/` per pack, move pack files into them
4. For each Run: leave outputs in place but record `output_folder_id` = parent folder of existing file (a synthetic per-run folder, OR keep flat for legacy and only new runs use the new layout)

The migration is shippable separately from the code changes — code reads the new fields if present, falls back to the old ones if not.

---

## Sequence (proposed sprints)

### Sprint G1 — Data model + new Drive layout (2-3 days)
- `drive_service.ensure_model_folder(code)`, `ensure_pack_folder(project, code)`, `ensure_run_folder(project, ts, pack, tpl)`
- New Model upload flow stores file in Drive, sets `drive_folder_id` + `drive_file_id`
- New Pack upload uses per-pack folder
- New Run creates per-run output folder; output xlsx goes there; `output_folder_id` set
- Migration script for existing data
- Tests

### Sprint G2 — UX surfaces (2-3 days)
- Models page: Drive-folder column, Open-in-Sheets via Drive URL
- Model detail page (NEW): folder, calculations history, version history panel
- ProjectView header: Drive folder link
- AssumptionPack revision-history panel (uses Drive revisions API)
- RunDetail: folder URL + artifacts list
- Backend endpoints: `GET /api/.../revisions`, `POST /api/.../revisions/{id}/restore`

### Sprint G3 (optional, only if needed) — Bulk re-org tools
- "Move project to a different Drive root" UI (for users who want their own root)
- "Export project as zip" download (everything in the project folder)
- "Archive project to cold storage" (move folder to a separate archive root)

---

## Specific decisions I'd want your input on before coding

1. **Folder name for the project namespace**: I proposed `Projects/{code}/` — but this adds a layer. Alternative: keep them flat under `MastekoFM/` like today (which is what the seed currently does). The flat version is fewer clicks; the nested version makes the top of `MastekoFM/` cleaner. **My recommendation: nest under `Projects/`**.

2. **Per-run folder naming**: `{YYYYMMDD-HHMMSS}_{pack_code}_{tpl_code}/` is sortable + tells you what it is at a glance, but ugly. Alternative: just `{run_id}/` (8-char prefix) — uglier as a name but matches what Firestore tracks. **My recommendation: timestamped name, with `run_id` stored in Firestore as the canonical identifier**.

3. **Versioning UI**: I proposed using Drive's native revision history (cleaner Drive UI, but versions invisible until you open the file). Alternative: keep a `v1/`, `v2/`... subfolder structure (clutters the Drive UI but each version is a browsable file). **My recommendation: Drive revisions + an in-app "version history" panel that exposes them**.

4. **Migrate existing runs?** Old runs have flat `Outputs/{ts}_*.xlsx` files. Re-organizing them into per-run folders is doable but disruptive (all existing `output_download_url`s get rewritten). Alternative: leave old runs as-is, only new runs use the new layout. **My recommendation: leave old runs flat, mark them `output_folder_id=null` (the UI shows "legacy run"). New runs use the new layout from day one**.

5. **Models in Drive — backward compat with existing GCS Models?** Hello World's model is in GCS today. I can:
   - (a) Keep both: Models can be GCS-backed OR Drive-backed; new ones go to Drive
   - (b) Migrate: upload all GCS-backed models to Drive, deprecate GCS
   
   **My recommendation: (a) for V1, (b) once we have at least one user with stable workflows. The pack_store already handles both via `load_model_bytes_compat` so the engine doesn't care.**

---

## Open questions

- **Do you want a "Calculations folder" UI link on the Models page that goes to a literal Drive folder?** I described it as a query view (filter Runs by Model). If you want a literal folder, we'd need to also COPY each Run's output into a `Models/{code}/Calculations/` folder — duplicating storage. The query-view approach avoids the duplication.

- **Should pack revision restore create a NEW v(N+1) or replace v(N)?** "Make current" rewinds — but Drive keeps the prior revision in history regardless. If we bump version on restore, the version number doesn't strictly correspond to file content (v3 might equal v1's bytes). I'd default to "bump" — version numbers are monotonic regardless of restore activity, and the UI shows what each version's content was.

- **Do you want a "Recent activity" feed on each Project page?** "User X uploaded pack v3 at 2026-04-27 14:30; User Y triggered run X at 14:35; etc." Out of scope for this proposal but a natural Sprint G3 thing.

---

## Reaction-needed checklist

Before I code, please react to:

- [ ] Folder hierarchy diagram (look at the "Proposed structure" tree above — does it match your mental model?)
- [ ] Decision #1 (nest under `Projects/` or stay flat)
- [ ] Decision #2 (run folder naming)
- [ ] Decision #3 (Drive revisions vs subfolders for versions)
- [ ] Decision #4 (migrate old runs vs leave legacy)
- [ ] Decision #5 (Models keep GCS dual support or Drive-only)
- [ ] Open question: Models calculations folder = literal vs query view

If you say "go with your recommendations," I run with them. If you want to adjust any decision, tell me which and what to.

---

## Effort estimate

- **Sprint G1** (data model + folders + migration): 2-3 days
- **Sprint G2** (UX surfaces + revision history endpoints): 2-3 days
- **Sprint G3** (bulk tools, optional): 1-2 days

**Total**: 4-6 days for G1+G2 to land everything you described. G3 deferred until you tell me you want it.

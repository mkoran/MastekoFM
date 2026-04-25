# MastekoFM — Session Handoff

> Last updated: 2026-04-16
> Live DEV version: 1.034
> Branch: `epic/excel-template-mvp`
> Phase: pre-Sprint-A (full plan committed; awaiting go-ahead to start Sprint A)

---

## Where we are

We just finished a major **redesign + planning pass** that pivots MastekoFM from a single-Template-per-Project model to a three-way composition platform:

```
AssumptionPack  ×  Model  ×  OutputTemplate  →  Run  →  Output artifact
```

The pivot is documented in [docs/REDESIGN_2026_04.md](docs/REDESIGN_2026_04.md), the architecture in [ARCHITECTURE.md](ARCHITECTURE.md), and the implementation plan in [BACKLOG.md](BACKLOG.md). Eight sprints are scoped in [docs/sprints/](docs/sprints/).

**Nothing has been deleted yet.** The current DEV (v1.034) still works exactly as before. The next step is Sprint A — a working Hello World vertical slice built alongside the legacy code so Marc can review the new UI before Sprint B does the deletes.

---

## What's currently working on DEV (v1.034)

Sign in at https://dev-masteko-fm.web.app with Google (any domain — OAuth is in Production mode).

| Feature | Status |
|---|---|
| Excel Template upload (case-sensitive `I_`/`O_` tab classification) | ✅ |
| Excel Project create/list | ✅ |
| Scenario create — GCS-backed or Drive-backed (Office mode editable) | ✅ |
| **"Edit in Google Sheets"** opens scenario .xlsx in Sheets without conversion | ✅ |
| Calculate: overlay scenario I_ tabs onto Template, LibreOffice recalc | ✅ |
| Run history with input file + output download links | ✅ |
| Settings: Drive folder picker, storage-kind default, Test Drive Connection | ✅ |
| Multi-domain Google Sign-In | ✅ |
| `firebase.json` no-cache index.html + immutable assets | ✅ |
| Custom header `X-MFM-Drive-Token` (avoids Fastly stripping `X-Google-*`) | ✅ |
| API client polls for Firebase token (3s window, fixes auth race) | ✅ |
| 102/102 backend tests passing | ✅ |
| ruff clean | ✅ |
| CI green on `epic/excel-template-mvp` | ✅ |

### Verified live on DEV

- Campus Adele Project (id: `WILJkqx44RYhtberWGSV`) with Base + Optimistic + Drive Test scenarios
- Drive Test scenario: Drive-backed, calculated successfully (~18s), output produced full workbook, opens in Sheets in Office mode

### Known limitations to be addressed by upcoming sprints

| Limitation | Resolved by |
|---|---|
| Project↔Template is rigidly 1:1 | Sprint A (three-way composition) |
| No OutputTemplate concept; output = full Model workbook | Sprint A |
| Calculate is synchronous (~17s blocks the request) | Sprint C |
| No PDF/Word/Google Doc outputs | Sprints D / H |
| No multi-user permissions (any signed-in user sees all projects) | Sprint E |
| Legacy TGV nav still in code behind `?legacy=1` flag | Sprint B (delete) |
| Existing Optimistic/Base scenarios are GCS-backed, not Drive-backed | Sprint B (re-seed) |

---

## What changed in this session

1. **Redesigned the system** from "one Template per Project" to "three-way composition `(AssumptionPack × Model × OutputTemplate)`"
2. **Introduced the `M_*` tab prefix** for OutputTemplate inputs (cells filled by Model `O_*` outputs) — see [docs/architecture/tab_prefix_contract.md](docs/architecture/tab_prefix_contract.md)
3. **Designed the Hello World vertical slice** — three tiny .xlsx files that exercise the entire pipeline
4. **Wrote 8 sprint plans** covering the full path from Hello World → Cleanup → Async → PDF → Multi-user → JSON packs → Sensitivity → Word/GoogleDoc
5. **Captured the strategic context** in [docs/REDESIGN_2026_04.md](docs/REDESIGN_2026_04.md) so a new dev/agent understands the "why"
6. **Documented every architectural decision** in ARCHITECTURE.md § 13 (Standing decisions table)
7. **Updated CLAUDE.md** with new development rules: tab-prefix discipline, three-way validation, async runs, custom-header gotcha, cache-control rules

---

## What to do next

### Immediate next step

Start **Sprint A — Hello World vertical slice**.

Detailed plan: [docs/sprints/SPRINT_A_helloworld_slice.md](docs/sprints/SPRINT_A_helloworld_slice.md)

Estimated effort: ~5 days
Branch off: `epic/excel-template-mvp`
Branch name: `epic/sprint-a-helloworld`

After Sprint A is deployed to DEV, Marc reviews the UI walkthrough. If the three-way composition feels right, proceed to Sprint B (cleanup). If not, iterate on the UX before deleting anything.

### Sprint A first task

- A-001: Create `seed/helloworld/` with three tiny .xlsx files
  - `helloworld_model.xlsx` — `I_Numbers` (a, b), `Calc` (sum, product), `O_Results` (sum, product)
  - `helloworld_inputs.xlsx` — `I_Numbers` only with a=5, b=7
  - `helloworld_report.xlsx` — `M_Results` (placeholder cells), `O_Report` (final output: "Sum: 12, Product: 35, Total: 47")

These files become both seed data AND test fixtures. Commit them to the repo.

---

## Key file locations (for the next dev/agent)

| File | Purpose |
|---|---|
| [README.md](README.md) | Top-level pitch + quick links |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full architecture, data model, repo layout, standing decisions |
| [BACKLOG.md](BACKLOG.md) | All 8 sprints with story-level breakdown |
| [CLAUDE.md](CLAUDE.md) | Mandatory development rules (tab discipline, deploys, git, etc.) |
| [LESSONS_LEARNED.md](LESSONS_LEARNED.md) | Bugs and gotchas inherited from MastekoDWH + this session's lessons |
| [docs/REDESIGN_2026_04.md](docs/REDESIGN_2026_04.md) | Strategic context for the pivot |
| [docs/architecture/three_way_composition.md](docs/architecture/three_way_composition.md) | The composition pattern explained |
| [docs/architecture/tab_prefix_contract.md](docs/architecture/tab_prefix_contract.md) | Tab naming + author rules |
| [docs/architecture/run_pipeline.md](docs/architecture/run_pipeline.md) | The two-stage execution algorithm |
| [docs/sprints/SPRINT_A_helloworld_slice.md](docs/sprints/SPRINT_A_helloworld_slice.md) | Imminent next sprint |
| `backend/app/services/excel_template_engine.py` | The engine (overlay, classify, validate). DO NOT regress. |
| `backend/app/services/scenario_store.py` | Will be renamed to `pack_store.py` in Sprint B; pattern stays |
| `backend/app/routers/excel_templates.py` | Will be renamed to `models.py` in Sprint B |
| `backend/app/routers/scenarios.py` | Will be renamed to `assumption_packs.py` in Sprint B |
| `backend/app/routers/excel_projects.py` | Will be renamed to `projects.py` in Sprint B (and slimmed) |
| `firebase.json` | Cache-control config — DO NOT remove the headers block |
| `frontend/src/services/api.ts` | Token-wait + custom header — DO NOT regress |

---

## Git state

```
Branch: epic/excel-template-mvp
Most recent commits:
  d7890b9 feat: Settings usability — Drive folder link, refresh-sign-in; no-cache index.html
  e5e5e94 fix: rename OAuth header X-Google-Access-Token -> X-MFM-Drive-Token
  ca90ac0 debug: log headers on /api/settings/test-drive (then removed)
  783dfd8 fix: wait up to 3s for Firebase token before API call + ExcelProjectView token dep
  30fcfa5 feat: dual-storage Scenarios (GCS + Drive .xlsx), Edit in Sheets
  546f6ae chore: bump version to 1.029
  8dc43de feat: Excel Template MVP — tab-prefix architecture (I_/O_/calc)
```

The next planning commit (this session) will add ~12 markdown files documenting the redesign and sprints.

---

## Running locally

```bash
cd "/Users/marckoran/My Drive (marc.koran@gmail.com)/MASTEKO/MSKCompanies/MarcKoran/CURSOR_AI/MastekoFM"
source .venv/bin/activate
pytest                          # 102/102 should pass
ruff check backend tests        # All checks passed
cd frontend && npm run build    # Should build clean

# To run the whole stack locally:
DEV_AUTH_BYPASS=true uvicorn backend.app.main:app --reload &
cd frontend && npm run dev
```

---

## Continuing from Cursor

```bash
cd "/Users/marckoran/My Drive (marc.koran@gmail.com)/MASTEKO/MSKCompanies/MarcKoran/CURSOR_AI/MastekoFM"
claude --continue
```

# MastekoFM

> A financial modeling operating system. Compose `(Assumptions × Model × OutputTemplate)` into reproducible, versioned reports.

---

## What it is

MastekoFM separates the three independently-versioned things a financial model is made of:

1. **AssumptionPack** — the numbers and tables a user wants to model
2. **Model** — the spreadsheet-based computation engine (with formulas)
3. **OutputTemplate** — the shape of the report a user wants to produce

Users compose a **Run** by picking one of each. The platform validates compatibility, executes the calculation, renders the output in the requested format (.xlsx, PDF, .docx, Google Doc), and stores everything for full reproducibility.

Excel is **just the calculation engine**. The platform — not Excel — is the source of truth.

---

## Quick links

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full technical architecture |
| [BACKLOG.md](BACKLOG.md) | Sprints A–H + Phase 3 backlog |
| [CLAUDE.md](CLAUDE.md) | Mandatory development rules |
| [SESSION_HANDOFF.md](SESSION_HANDOFF.md) | Current state + next steps |
| [LESSONS_LEARNED.md](LESSONS_LEARNED.md) | Hard-won bugs and gotchas |
| [docs/REDESIGN_2026_04.md](docs/REDESIGN_2026_04.md) | Why we pivoted from the v1 design |
| [docs/architecture/](docs/architecture/) | Deep-dive design docs |
| [docs/sprints/](docs/sprints/) | Per-sprint detailed plans |

---

## The three-way model in one diagram

```
                  AssumptionPack (.xlsx with I_* tabs)
                         │
                         ▼ Stage 1: overlay onto Model.I_*
                       Model (.xlsx with I_/O_/calc tabs)
                         │
                         ▼ recalc, extract Model.O_*
                  OutputTemplate (.xlsx with M_/calc/O_  OR  .pdf/.docx/.gdoc)
                         │
                         ▼ Stage 2: inject into M_*, recalc/render
                       Output (downloadable artifact)
```

The complete pattern: [docs/architecture/three_way_composition.md](docs/architecture/three_way_composition.md).

---

## Tab-prefix contract

Every `.xlsx` file MastekoFM touches uses **case-sensitive** tab prefixes:

- `I_*` — input tab, filled by an AssumptionPack
- `O_*` — output tab, published by a Model
- `M_*` — model-output tab, filled by Model's `O_*` values (only on OutputTemplates)
- (other) — calculation tab, never touched

`I_Inputs & Assumptions` is an input. `i_Cap Table` (lowercase) is a calc tab.

The full contract: [docs/architecture/tab_prefix_contract.md](docs/architecture/tab_prefix_contract.md).

---

## Stack

| Layer | Tech |
|---|---|
| Backend API | Python 3.12, FastAPI |
| Workers (async runs) | Same image, separate Cloud Run service |
| Excel engine | openpyxl + LibreOffice headless |
| Database | Firestore |
| File storage | Google Drive (`.xlsx`) + GCS (output mirrors) |
| Auth | Firebase Auth (Google Sign-In) |
| Job queue | Cloud Tasks |
| Frontend | React 19, TypeScript, Vite, Tailwind |
| Hosting | Firebase Hosting |
| CI/CD | Cloud Build, deploy-dev.sh / deploy-prod.sh |

---

## Running locally

```bash
# Backend
cd backend
python3.12 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
DEV_AUTH_BYPASS=true uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Deploying

```bash
./deploy-dev.sh        # auto-bumps VERSION, builds, deploys both Cloud Run + Firebase Hosting (DEV)
./deploy-prod.sh       # promotes the DEV image to PROD; explicit human approval required
```

## Tests

```bash
cd MastekoFM
source .venv/bin/activate
pytest                 # backend; should be green on every commit
ruff check backend tests
cd frontend && npm run lint && npm run build
```

---

## Repo layout

See [ARCHITECTURE.md § 9](ARCHITECTURE.md) for the full project structure.

```
MastekoFM/
├── README.md                    ← you are here
├── ARCHITECTURE.md
├── BACKLOG.md
├── CLAUDE.md
├── LESSONS_LEARNED.md
├── SESSION_HANDOFF.md
├── VERSION
├── backend/                     ← FastAPI app + LibreOffice
├── frontend/                    ← React app
├── seed/                        ← committed seed .xlsx files (Hello World, Campus Adele)
├── tests/                       ← pytest + fixtures
├── docs/                        ← architecture + sprint plans
├── firebase.json                ← hosting + cache-control
├── cloudbuild.yaml
├── deploy-dev.sh
└── deploy-prod.sh
```

---

## License

See [LICENSE](LICENSE).

---

## Status

- **Live DEV**: https://dev-masteko-fm.web.app (v1.034 as of 2026-04-16)
- **GitHub**: [github.com/mkoran/MastekoFM](https://github.com/mkoran/MastekoFM)
- **Active branch**: `epic/excel-template-mvp` (will be merged into main after Sprint B)
- **Next milestone**: Sprint A — Hello World vertical slice (~5 days)

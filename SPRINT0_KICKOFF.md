# MastekoFM — Claude Code Session 1: Sprint 0 Kickoff

## Context

You are bootstrapping a new SaaS product called **MastekoFM** (Financial Modelling Platform). This project follows the same GCP + Firebase + Cloud Run architecture as MastekoDWH, but is a **separate GCP project** with its own infrastructure.

The owner is Marc Koran (marc.koran@gmail.com, marc@campushabitations.com).

## Step 1 — Read the reference project

The reference project is at: https://github.com/mkoran/MastekoDWH

Read these files and extract the specific things noted:

1. **CLAUDE.md** — Extract: local-first rules, commit discipline, deploy confidence gates, CI-red discipline, schema change policy, epic/branch discipline, standing authorizations. These rules apply to MastekoFM identically.

2. **deploy-dev.sh** — Extract: exact deploy sequence (version bump → build frontend → Cloud Build async + polling → Firebase deploy → health check → print summary without auto-commit). MastekoFM will follow the same sequence.

3. **deploy-prod.sh** — Extract: PROD deploy pattern (no version bump, Cloud Build with auto-rollback, resource settings update, Firebase deploy, verify, print tag reminder without auto-tag).

4. **cloudbuild.yaml** — Extract: CI pipeline steps (lint → test → build → push → deploy → smoke tests). MastekoFM will use the same structure.

5. **backend/Dockerfile** — Extract: multi-stage build pattern (base → test → prod). MastekoFM adds `libreoffice-calc-nogui` to the base stage.

6. **firebase.json** — Extract: hosting configuration pattern with /api rewrites to Cloud Run. MastekoFM gets its OWN entries (fm-dev, fm-prod), NOT added to MastekoDWH's firebase.json.

7. **pyproject.toml** — Extract: ruff config (single source of truth for lint rules), pytest config.

8. **.github/workflows/ci.yml** — Extract: GitHub Actions CI pattern (ruff + pytest backend, tsc + build frontend).

## Step 2 — Read the MastekoFM design documents

These four files are in the current working directory. Read them ALL before writing any code:

1. **CLAUDE.md** — The development rules for this project. Follow every rule marked with ⚡.
2. **ARCHITECTURE.md** — Full technical architecture, data model, workflows, and sprint plan.
3. **BACKLOG.md** — 173-item product backlog across 18 domains.
4. **LESSONS_LEARNED.md** — Hard-won patterns from MastekoDWH. Reference when making infrastructure decisions.

## Step 3 — Create the GitHub repository

Create the repository `MastekoFM` under the `mkoran` GitHub account. Initialize with:
- README.md (project title + one-line description + "Last reviewed" marker)
- .gitignore (Python + Node + macOS + .env)
- MIT license

## Step 4 — Create the GCP project and infrastructure

**GCP Project:** `masteko-fm` (NEW project, separate from `masteko-dwh`)
**Region:** `northamerica-northeast1` (Montréal)

### 4a. Create GCP project
```bash
gcloud projects create masteko-fm --name="MastekoFM"
gcloud config set project masteko-fm
```
Link billing to the same billing account as masteko-dwh.

### 4b. Enable required APIs
```bash
gcloud services enable \
  drive.googleapis.com \
  sheets.googleapis.com \
  bigquery.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  firebase.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com
```

### 4c. Create service account
```bash
gcloud iam service-accounts create masteko-fm-sa \
  --display-name="MastekoFM Service Account"

for ROLE in \
  roles/bigquery.admin \
  roles/datastore.user \
  roles/secretmanager.secretAccessor \
  roles/cloudtasks.enqueuer \
  roles/run.invoker \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding masteko-fm \
    --member="serviceAccount:masteko-fm-sa@masteko-fm.iam.gserviceaccount.com" \
    --role="$ROLE"
done
```

### 4d. Create claude-dev service account (for Claude Code deploys)
Follow the same pattern as MastekoDWH's `docs/DEPLOY.md` claude-dev setup:
```bash
gcloud iam service-accounts create claude-dev \
  --display-name="Claude Code DEV deployer"
```
Grant the same DEV-scoped IAM roles that MastekoDWH's claude-dev has.

### 4e. Create infrastructure
```bash
# Artifact Registry
gcloud artifacts repositories create masteko-fm \
  --repository-format=docker \
  --location=northamerica-northeast1

# Cloud Tasks queue
gcloud tasks queues create fm-jobs --location=northamerica-northeast1

# Firestore database
gcloud firestore databases create --location=northamerica-northeast1

# BigQuery dataset
bq mk --dataset --location=northamerica-northeast1 masteko-fm:masteko_fm
```

### 4f. Firebase setup
```bash
firebase projects:addfirebase masteko-fm
# Create hosting sites:
firebase hosting:sites:create dev-masteko-fm --project masteko-fm
firebase hosting:sites:create masteko-fm --project masteko-fm
# Enable Firebase Auth with Google Sign-In via Firebase Console
```

### 4g. Google Drive
Create root folder `MastekoFM/` in Marc's Google Drive. Note the folder ID.

## Step 5 — Scaffold the repository

Create the full directory structure from ARCHITECTURE.md's "Repository structure" section. Every file should exist, even if it's a stub. Specifically:

### 5a. Backend skeleton
- `backend/Dockerfile` — Multi-stage (base with `libreoffice-calc-nogui` + test + prod)
- `backend/requirements.txt` — FastAPI, uvicorn, openpyxl, google-cloud-bigquery, google-cloud-firestore, google-api-python-client, google-auth, python-dotenv, pydantic, cryptography
- `backend/app/main.py` — FastAPI app with CORS, health router mounted
- `backend/app/config.py` — Pydantic Settings class loading from env + Secret Manager
- `backend/app/middleware/auth.py` — Firebase Auth middleware with DEV bypass
- `backend/app/routers/health.py` — `GET /health` (simple) + `GET /api/health/full` (all subsystems)
- `backend/app/models/` — Empty `__init__.py` for each model file listed in ARCHITECTURE.md
- `backend/app/routers/` — Empty stubs for each router listed in ARCHITECTURE.md
- `backend/app/services/` — Empty stubs for each service listed in ARCHITECTURE.md

### 5b. Frontend skeleton
- `frontend/package.json` — React 19, TypeScript, Vite, Tailwind CSS, React Router, TanStack Table, React Flow, Recharts
- `frontend/vite.config.ts` — With proxy config (localhost:8080 for /api)
- `frontend/tailwind.config.ts`
- `frontend/tsconfig.json`
- `frontend/src/App.tsx` — Router with protected routes
- `frontend/src/pages/Dashboard.tsx` — Stub page
- `frontend/src/services/api.ts` — API client stub

### 5c. Deploy infrastructure
- `VERSION` — `1.000`
- `run.sh` — Unified CLI (local/dev/prod)
- `deploy-dev.sh` — Following MastekoDWH pattern exactly (async Cloud Build + polling)
- `deploy-prod.sh` — Following MastekoDWH pattern exactly (promote, auto-rollback)
- `cloudbuild.yaml` — Multi-stage pipeline (lint → test → build → push → deploy → smoke)
- `firebase.json` — DEV + PROD hosting targets with /api rewrites
- `.firebaserc` — Project targets
- `pyproject.toml` — ruff + pytest config (single source of truth)
- `.github/workflows/ci.yml` — GitHub Actions (ruff + pytest + tsc + build)

### 5d. Documentation
- `CLAUDE.md` — Already provided (copy from working directory)
- `ARCHITECTURE.md` — Already provided (copy from working directory)
- `BACKLOG.md` — Already provided (copy from working directory)
- `LESSONS_LEARNED.md` — Already provided (copy from working directory)
- `SESSION_HANDOFF.md` — Initial version with project overview and file locations
- `docs/epics/` — Empty directory for future epic files

### 5e. Skills
- `skills/SKILL_excel_engine.md` — Stub with section headers
- `skills/SKILL_dag_execution.md` — Stub with section headers
- `skills/SKILL_datasource_connectors.md` — Stub with section headers
- `skills/SKILL_report_generation.md` — Stub with section headers

### 5f. Tests
- `tests/test_health.py` — Test health endpoints return 200
- `tests/test_config.py` — Test VERSION format matches MAJOR.NNN
- `tests/conftest.py` — Shared fixtures

## Step 6 — Local verification

Before ANY deployment:

1. `cd frontend && npm install && npm run build && cd ..`
2. Create `.venv`: `/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv`
3. `.venv/bin/pip install -r backend/requirements.txt`
4. `.venv/bin/pip install pytest ruff`
5. `.venv/bin/ruff check backend/ tests/`
6. `.venv/bin/python -m pytest tests/ -v`
7. Start backend: `.venv/bin/python -m uvicorn backend.app.main:app --port 8080`
8. Verify: `curl -s http://localhost:8080/health`

ALL must pass before proceeding.

## Step 7 — Initial commit and push

1. `git init`
2. `git remote add origin https://github.com/mkoran/MastekoFM.git`
3. Propose commit message: `feat: Sprint 0 — project skeleton with full infrastructure`
4. Wait for approval before committing
5. Push to `main`
6. Verify CI passes within 5 minutes

## Step 8 — First DEV deploy

1. Run `./deploy-dev.sh`
2. Verify:
   - Cloud Build succeeds
   - `curl -s https://masteko-fm-api-dev-<hash>.a.run.app/health` returns 200
   - `curl -s https://masteko-fm-api-dev-<hash>.a.run.app/api/health/full` shows all green
   - Firebase Hosting dev site loads
3. Report results

## Definition of Done

All of the following must be true:

- [ ] GitHub repo `mkoran/MastekoFM` exists with full directory structure
- [ ] GCP project `masteko-fm` provisioned with all APIs enabled
- [ ] Service accounts created (masteko-fm-sa + claude-dev)
- [ ] Artifact Registry, Cloud Tasks queue, Firestore, BigQuery dataset created
- [ ] Firebase project with DEV + PROD hosting sites
- [ ] Google Drive `MastekoFM/` folder created
- [ ] Backend starts locally and health check returns 200
- [ ] Frontend builds with zero errors
- [ ] `ruff check` passes with zero errors
- [ ] `pytest` passes with zero failures
- [ ] GitHub Actions CI is green on main
- [ ] DEV deploy successful (Cloud Run + Firebase Hosting)
- [ ] `deploy-dev.sh` VERSION bump works correctly (1.000 → 1.001)
- [ ] All four design documents (CLAUDE.md, ARCHITECTURE.md, BACKLOG.md, LESSONS_LEARNED.md) committed
- [ ] SESSION_HANDOFF.md created and accurate

When complete, say:
**"Sprint 0 complete. Skeleton deployed to DEV. All checks passing. Ready for Sprint 1 on your approval."**

---

## Environment details

- Python 3.12: `/opt/homebrew/opt/python@3.12/bin/python3.12`
- Node.js 20+ installed
- gcloud CLI authenticated (run `gcloud config get-value account` to verify)
- Firebase CLI installed (`firebase --version`)
- GitHub CLI installed (`gh --version`)

## Important reminders

- Read CLAUDE.md FIRST — it contains rules that prevent common mistakes.
- The ⚡ marked rules in CLAUDE.md come from real production bugs in MastekoDWH. Do not skip them.
- GCP region is `northamerica-northeast1` (Montréal), NOT `us-central1`.
- This is a NEW GCP project. Do not touch anything in `masteko-dwh`.
- Do not deploy to PROD without explicit approval.
- Do not auto-commit or auto-tag.

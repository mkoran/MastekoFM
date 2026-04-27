# CLAUDE.md — MastekoFM Development Rules

> These rules are MANDATORY for all Claude Code sessions working on MastekoFM.
> Violations require immediate correction before continuing.
>
> This file inherits hard-won lessons from MastekoDWH (v3.007, 421+ tests,
> 3 epics shipped to production). Rules marked with ⚡ were added because
> something broke without them.

## Owner

- Marc Koran (marc.koran@gmail.com, marc@campushabitations.com)
- Python 3.12: `/opt/homebrew/opt/python@3.12/bin/python3.12`
- Node.js 20+ installed
- gcloud CLI authenticated

## Project identity

- **Product**: MastekoFM — Financial Modelling Platform
- **GCP Project**: `masteko-fm`
- **Region**: `northamerica-northeast1` (Montréal)
- **GitHub**: `github.com/mkoran/MastekoFM`

---

## Testing Protocol — MANDATORY before presenting any change

1. **Never tell the user something is "done" until you've verified it yourself.** ⚡
2. **Backend changes:** After any change, call affected endpoints with `curl` and verify the response.
3. **Frontend changes:** Verify the UI renders correctly and console has no errors.
4. **If you cannot test something**, say so upfront with the reason. Never claim it works if you haven't confirmed. ⚡
5. **If a test fails, fix it before presenting.** Never ship known-broken code.
6. **Verification checklist for every deploy:**
   - [ ] `npm run build` passes with zero errors
   - [ ] Backend health check returns 200
   - [ ] Affected API endpoints return expected responses (curl)
   - [ ] Frontend loads without console errors
   - [ ] Specific feature tested end-to-end where possible

---

## Local-First Development Policy (ENFORCED)

### Core Rule (Non-Negotiable)

All development, validation, and testing MUST occur locally before any remote or deployment action.
If a task can be completed locally, it is forbidden to use a remote environment.

### Mandatory Workflow

1. Modify code locally
2. Run local validation: unit tests (pytest), lint (ruff), type checks, local app startup
3. Fix all issues
4. Re-run validation until clean
5. Summarize changes
6. Propose commit (DO NOT auto-commit)
7. Wait for approval
8. ONLY THEN consider deployment

Skipping steps is not allowed.

---

## Standing Authorizations (DEV environment)

⚡ *Learned from MastekoDWH: requiring per-action DEV approval is friction without benefit. DEV is exactly where Claude should be free to push, deploy, break things, and iterate.*

**Pre-approved without asking:**
- Running `./deploy-dev.sh` end-to-end
- Any `gcloud` command targeting `*-dev` resources
- `firebase deploy --only hosting:dev`
- Creating, modifying, or deleting data in `dev_*` Firestore collections
- `git push` of any branch OTHER THAN `main`
- Reading any DEV resource for diagnostics

**After any DEV deploy, Claude must:**
1. Verify the action succeeded (curl health endpoints, check logs)
2. Report the outcome in plain text to the user
3. Check CI status within 5 minutes of any push

### Absolute Prohibitions (Without Explicit Per-Action Approval)

- Running `./deploy-prod.sh` or any `gcloud` against `*-prod`
- `firebase deploy --only hosting:prod`
- `git push origin main` or `git push` while on `main`
- `git push --force` to ANY branch, ever ⚡
- Creating, modifying, or deleting data in `prod_*` Firestore collections
- Touching Secret Manager for prod-scoped secrets
- Creating new GCP resources (services, buckets, queues)
- Modifying GCP IAM policies, service accounts, or roles
- `git tag -f` (overwriting existing tags) ⚡

**Why the asymmetry:** DEV is recoverable. If Claude deploys broken code to DEV, just deploy the fix. PROD is not — real users, real data, some actions irrecoverable.

---

## Commit Discipline

- Never auto-commit. Never auto-push. ⚡
- Always summarize changes before proposing commit.
- Only propose commit after all local checks pass.
- Deploy scripts never auto-commit VERSION bumps or auto-create git tags. ⚡

---

## Post-Push Verification & CI-Red Discipline

⚡ *Learned from MastekoDWH: CI on main had been silently failing for 3+ consecutive commits before anyone noticed. Root causes: lint config diverged between local and CI, npm peer dependency conflicts, GitHub Actions referenced secrets that never existed.*

### Rule 1 — Verify CI status within 5 minutes of every push
Do NOT push and walk away. Do NOT assume "tests passed locally" means CI is green.

### Rule 2 — CI red on main is P0
Stop everything else and fix it before doing anything else. No new feature work, no doc updates.

### Rule 3 — Single source of truth for tooling configs ⚡

| Tool | Canonical config | Forbidden |
|---|---|---|
| ruff | `pyproject.toml [tool.ruff.lint]` | passing `--select` or `--ignore` from CI files |
| pytest | `pyproject.toml [tool.pytest.ini_options]` | passing rules via CI env |
| TypeScript | `frontend/tsconfig.json` | passing rules via CI flags |

CI files invoke tools with minimum flags only. If a rule needs to be different, fix the config, not the invocation.

### Rule 4 — No workflow may reference a secret that doesn't exist ⚡
Verify secrets exist in repo settings BEFORE merging any workflow that references them.

### Rule 5 — No tolerating partial green ⚡
"Backend green but frontend red" is NOT green. All workflows must be green.

---

## Environment Separation

| Environment | Backend | Frontend | Firestore | Auth |
|---|---|---|---|---|
| LOCAL | localhost:8080 | localhost:5173 | Firestore emulator | Auth bypass |
| DEV | masteko-fm-api-dev (Cloud Run) | dev-masteko-fm (Firebase Hosting) | `dev_` prefix | Firebase Auth |
| PROD | masteko-fm-api-prod (Cloud Run) | masteko-fm (Firebase Hosting) | `prod_` prefix | Firebase Auth |

**Local** = development, debugging, unit tests.
**Dev/Cloud** = integration, deployment validation only.
Dev environment MUST NOT be used for basic testing.

---

## Epic & Branch Discipline

⚡ *Carried forward from MastekoDWH where this pattern was proven across 3 epics (CI-00, SCHEMA-00, RBAC).*

- Every non-trivial feature gets an epic file in `docs/epics/`
- Branch per epic: `epic/{epic-id}-{short-name}`
- One commit per story (not per file) — `git revert <sha>` rolls back a whole story
- Epic branches deploy to DEV freely, NEVER to PROD
- Merge with `--no-ff` so the merge commit is a clean revert boundary
- An epic is not "done" until every story is validated live on DEV
- Tag every PROD deploy: `prod-v{VERSION}` (MAJOR.NNN format)

### Version format
- `MAJOR.NNN` (e.g., `1.000`, `1.042`)
- deploy-dev.sh auto-bumps counter. deploy-prod.sh promotes, does NOT bump.
- Git SHA captured separately via Cloud Build, surfaced via `/api/version`.
- Never `git tag -f` — prior PROD revision must remain identifiable for rollback.

---

## Schema Change Policy

⚡ *From MastekoDWH: learned that additive-only schema changes are the only safe default when you have production data.*

### Hard rules
1. **Additive-only by default.** New fields, new collections are safe. Never remove a field that app code reads.
2. **Renames are two-step.** Add new → backfill → dual-write → switch reads → remove old.
3. **Every migration is idempotent.** Running it twice must be safe.
4. **App code must tolerate old documents.** Always use `.get('field', default)`, never `doc['field']`. ⚡
5. **Snapshot production before migrating.** Firestore export + BQ dataset copy.

---

## Deploy Confidence Gates

⚡ *From MastekoDWH: "A deploy is not done the moment Cloud Run accepts the new revision. It is done when the deployed service has been verified to work against live infrastructure."*

### Required checks on every deploy
1. Lint + unit tests pass (Cloud Build)
2. Container builds and pushes successfully
3. Schema migrations applied successfully
4. Cloud Run revision accepted and serving
5. Smoke tests pass: `GET /health`, `GET /api/health/full`, `GET /api/version`
6. PROD only: automatic rollback if any check fails

### Rules
- Never bypass smoke tests. Fix the tests or the code, not the pipeline.
- One canonical deploy path. Do not introduce parallel deploy mechanisms. ⚡
- Rollback must be a sub-60-second operation. Practice quarterly.

---

## Documentation Freshness Policy

⚡ *From MastekoDWH: Python version, test counts, entity counts, and deploy mechanisms all drifted across multiple documents without anyone noticing.*

### Watched documents

| Document | Audience |
|---|---|
| `README.md` | New contributor |
| `ARCHITECTURE.md` | Engineer bootstrapping the project |
| `SESSION_HANDOFF.md` | Claude Code session continuity |
| `BACKLOG.md` | Product planning |

**Rule:** Every commit must consider these docs. If the commit changes something they describe, update them in the same commit. A "Last reviewed" marker older than 30 days means the contents are suspect.

---

## Continuous Standards Refinement ("Fix as you find")

⚡ *From MastekoDWH: 92 ruff errors, 5 stale documents, and 2 broken deploy mechanisms accumulated because nobody fixed them when they noticed.*

When you discover a bug, contradiction, or missing rule while doing other work — fix it in the same commit. Don't defer small fixes.

**But apply judgment:** if the fix would double the commit size or touch unrelated subsystems, open a backlog item instead.

---

## MastekoFM-Specific Rules

### Tab-prefix discipline (canonical, post-redesign 2026-04)

⚡ *This replaces the earlier "named ranges are the only interface" rule. Tab prefixes are simpler and proven.*

Every `.xlsx` file MastekoFM touches uses **case-sensitive** tab prefixes:

| Prefix | Meaning | Used on |
|---|---|---|
| `I_*` | Input tab — filled by an AssumptionPack | Model, AssumptionPack |
| `O_*` | Output tab — published by a Model | Model |
| `M_*` | Model-output tab — filled by Model's `O_*` values | OutputTemplate only |
| (other) | Calculation tab | Model, OutputTemplate |

**Strict case sensitivity** — `i_Cap Table` is a calc tab, NOT an input. Validators MUST use `str.startswith("I_")` (literal), never `.lower().startswith("i_")`.

**Compatibility rules** (auto-validated by `services/run_validator.py`):
1. AssumptionPack must contain every `I_*` tab declared on the Model
2. AssumptionPack must contain ONLY `I_*` tabs (no `O_*`, no `M_*`, no calc tabs — those are Model territory)
3. Every `M_<name>` tab in OutputTemplate must have a matching `O_<name>` tab in the Model

Full contract for template authors: [docs/architecture/tab_prefix_contract.md](docs/architecture/tab_prefix_contract.md).

### Excel files
- All .xlsx read/write operations use `openpyxl`
- All formula calculation uses **LibreOffice headless** — never openpyxl's formula evaluator
- Calculation flow: openpyxl overlays cells → save .xlsx → LibreOffice recalculates → openpyxl reads results
- Cell-copy overlay (NOT sheet replacement) preserves cross-tab formula integrity — proven on Campus Adele's 7,302 calc-tab formulas
- LibreOffice subprocess timeout: 60 seconds per stage (we run two stages: Model recalc + OutputTemplate recalc)
- Users can modify and re-upload .xlsx files; the validator runs again on every upload
- For Drive-backed files, "upload" = `drive.files.update` (preserves the file_id and Sheets edit URL)

### Three-way composition (NEW, post-redesign 2026-04)

A Run is an immutable record of `(AssumptionPack@vN, Model@vM, OutputTemplate@vO)` plus its computed output.

- AssumptionPacks live in Drive (`.xlsx`). NO GCS storage for packs (post-Sprint-B).
- Models live in Drive (`.xlsx`). One Model can be paired with many AssumptionPacks.
- OutputTemplates live in Drive (`.xlsx`, future: `.pdf` / `.docx` / Google Doc).
- Runs are top-level Firestore entities, not nested under a Project.
- Every Run records `*_drive_revision_id` for full reproducibility (re-fetch the exact bytes used).

### DAG operations
**DEPRECATED 2026-04**. The "DAG of spreadsheets" concept (where Sheet A's outputs feed Sheet B's inputs) was replaced by the three-way composition model. Cross-sheet references inside a single Model are handled natively by Excel formulas. The DAG router and dag_executor service will be deleted in Sprint B.

### Async execution discipline (Sprint C+)
- POST /api/runs returns 202 Accepted with `{run_id}` — never blocks
- Cloud Tasks queue (`mfm-runs-{env}`) delivers to a separate Cloud Run worker service
- Worker uses OIDC authentication (Cloud Tasks → /internal/tasks/run/{id}); reject Firebase tokens on internal endpoints
- Failed runs retry with exponential backoff (max 3); final failure leaves status=failed with error
- Frontend polls Run doc via Firestore onSnapshot for live status
- Separate compute-heavy work (spreadsheet calculation) from API serving ⚡ (lesson from MastekoDWH)

### AssumptionPacks (renamed from "Scenario" in redesign 2026-04)
- Every value change is captured by Drive's revision history (free, automatic)
- Each upload bumps the AssumptionPack `version` integer
- AssumptionPacks are IMMUTABLE per version — to change, you upload a new revision
- AssumptionPacks live in `<drive_root>/MastekoFM/<project>/Inputs/<pack_code>.xlsx`
- Archive (not delete) by setting `status=archived`; preserves Drive history
- Percentages stored as decimals (0.05, not 5) — applies to literal cells in I_ tabs

### OutputTemplates (renamed from "Reports" in redesign 2026-04)
- An OutputTemplate is the `.xlsx`/`.pdf`/`.docx`/Google Doc that shapes the final Run artifact
- For format=`xlsx`: same engine as Models (M_/calc/O_ tab convention); no separate renderer needed
- For format=`pdf`: HTML/CSS template + WeasyPrint (Sprint D)
- For format=`docx`: python-docx with placeholder substitution (Sprint H)
- For format=`google_doc`: Google Docs API copy + fill (Sprint H)
- All generated outputs go to Google Drive `Outputs/` folder + GCS mirror (stable URL)
- PDF generation must complete within 60 seconds (worker timeout)
- Each OutputTemplate declares its required Model outputs (auto-detected from `M_*` tab names)

### Data sources (rebuilt as AssumptionPack source connectors in Sprint F)
**Old Datasource code DELETED in Sprint B.** Will be rebuilt as part of JSON AssumptionPack support.
- Connector credentials stored in Secret Manager
- All sync operations are idempotent
- Sync errors must be recoverable (retry without data loss)
- Field mappings are explicit — never auto-map by name without user confirmation
- Batch API calls wherever possible ⚡ (MastekoDWH: 614 per-file API calls → 1 batch call)

### Firestore patterns ⚡
- Environment-prefixed collections: `dev_projects`, `prod_projects`
- Always `.get('field', default)` on Firestore documents, never `doc['field']`
- `display_name=None` from Firebase can break Pydantic strict mode — coerce None→"" in `from_firestore`
- Composite indexes needed for multi-field queries (error messages include direct creation links)
- Firestore security rules: deny-all from client by default. Backend uses Admin SDK (bypasses rules).
- Real-time listeners (onSnapshot) from frontend will need targeted rule openings.

### Auth patterns ⚡
- DEV auth bypass via `DEV_AUTH_BYPASS=true` env var. PROD must NEVER set this.
- Every API endpoint must have explicit auth decoration. No endpoint goes live without a category.
- UI hiding is NOT enforcement. Backend is always the source of truth.
- Firebase Auth tokens and Cloud Tasks OIDC tokens are separate auth paths.
- Last-admin protection: system must always have at least one admin.
- **Custom header `X-MFM-Drive-Token` (NOT `X-Google-*`)** ⚡ — Firebase Hosting's Fastly edge strips `X-Google-*` headers before they reach Cloud Run. We learned this the hard way (v1.030→1.032). All Drive-token-passing must use `X-MFM-Drive-Token`.
- **API client polls for token up to 3s before each request** ⚡ — fixes a race where components fire requests before Firebase's `onAuthStateChanged` sets the token. See `frontend/src/services/api.ts`.
- OAuth scope: `drive.file` (narrow, non-sensitive) — no Google verification required, app available to any Google domain.
- OAuth consent screen: External + In Production — multi-domain sign-in without test-user list.

### Hosting & cache discipline ⚡
- `firebase.json` sets `Cache-Control: no-cache, no-store, must-revalidate` on `/index.html`
- `/assets/**` (Vite-hashed filenames) cached `immutable, max-age=31536000`
- Reason: previously Firebase's default caching could serve stale `index.html` pointing at old JS hashes. Users would see a broken cached app forever. Fixed in v1.034.

---

## Infrastructure Patterns (from MastekoDWH)

### Dockerfile — multi-stage build ⚡
```
base    → shared deps (python:3.12-slim + requirements + libreoffice-calc-nogui)
test    → base + pytest + ruff → runs tests at build time
prod    → base only, no test deps, no tests/ directory
```
Test stage built first. If pytest fails, the whole build fails. Prod image stays lean.

### Cloud Build — async polling ⚡
Use `gcloud builds submit --async` + manual polling. Service accounts without project-wide log viewer permission cause `gcloud builds submit` to exit non-zero on successful builds, tripping `set -e`.

### Cloud Run settings (PROD)
- `--min-instances=1` — prevents cold-start latency
- `--no-cpu-throttling` — CPU available even when not processing requests
- Resource limits set explicitly in deploy script

### NPM in CI ⚡
- CI uses `npm ci` (clean install), stricter than `npm install`
- Peer dependency conflicts that `npm install` silently resolves will break `npm ci`
- Always test with `npm ci` locally before pushing

---

## Estimate & Scope Discipline

- T-shirt sizing: XS (<2h), S (half day), M (1–2 days), L (3–4 days), XL (1 week+)
- An epic containing an XL story should be split before starting
- Story effort includes validation time, not just coding time
- When in doubt, estimate one size larger and ship sooner

---

## Code Conventions

### Backend (Python)
- Python 3.12 (NOT 3.14 — gRPC incompatible) ⚡
- FastAPI for all API routes
- Pydantic v2 for request/response models
- Type hints on every function
- Docstrings on public functions
- `pytest` for all tests
- `ruff` for linting (config in pyproject.toml only)

### Frontend (TypeScript)
- React 19 with functional components and hooks
- TypeScript strict mode
- Tailwind CSS (no custom CSS unless necessary)
- TanStack Table for data grids
- React Flow for DAG editor
- Recharts for charts

### Git
- Branch from `main` for features: `feature/{description}`
- Branch from `main` for epics: `epic/{epic-id}-{short-name}`
- Merge `--no-ff` to main (preserves epic boundaries for revert)
- Commit messages: `type: description` (feat, fix, refactor, test, docs, chore)
- Never squash-merge epic branches ⚡

---

## Session Handoff

- At end of every Claude Code session, update `SESSION_HANDOFF.md`
- Include: what was done, what's next, any blockers, any decisions made
- `SESSION_HANDOFF.md` reads VERSION file for version — never hardcode

---

## When to Update This File

Update when:
- A new cross-cutting rule is agreed
- A new epic introduces a discipline that applies to all future work
- A rule has been debated and changed
- You discover a gap or ambiguity while doing other work (fix as you find)

Do NOT update for:
- One-off decisions for a single epic (those go in the epic file)
- Implementation details (those go in code comments)
- Temporary workarounds (those go in the epic's "Open questions")

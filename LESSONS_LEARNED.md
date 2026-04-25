# MastekoDWH — Lessons Learned for MastekoFM

> Extracted 2026-04-14 from MastekoDWH v3.007 project files.
> Every lesson below was learned from a real production bug, wasted session,
> or near-miss in the MastekoDWH project.

---

## 1. Hard rules that prevented disasters

### Testing protocol (non-negotiable)
- Never tell the user something is "done" until you've verified it yourself with curl/browser.
- If you can't test a third-party integration, say so explicitly — never claim it works if you haven't confirmed.
- If a test fails, fix it before presenting. Never ship known-broken code.
- Verification checklist for every deploy: `npm run build` passes, health check returns 200, affected endpoints respond correctly, frontend loads without console errors.

### Commit discipline
- Never auto-commit. Never auto-push. Always summarize changes before proposing.
- Deploy scripts never auto-commit VERSION bumps or auto-create git tags. The human reviews and commits.
- `git push --force` is NEVER allowed, even on feature branches, without explicit per-action approval.
- `git tag -f` is NEVER allowed — prior PROD revisions must remain identifiable for rollback.

### Schema change discipline
- Additive-only by default. Never DROP TABLE, DROP COLUMN, or remove a Firestore field that app code reads.
- Renames are two-step: add new → backfill → dual-write → switch reads → stop writing old.
- Every migration script must be idempotent (safe to run twice).
- App code must tolerate old documents: always use `.get('field', default)`, never `doc['field']`.
- Snapshot production Firestore before any migration.

### CI-Red discipline (learned the hard way)
- CI had been silently failing for 3+ consecutive commits before anyone noticed.
- Root causes: lint config diverged between local and CI, npm peer dependency conflicts, GitHub Actions referenced secrets that never existed.
- Rule: verify CI status within 5 minutes of every push. CI red on main is P0 — stop everything and fix.
- "Tests passed locally" does NOT mean CI is green. Local and CI environments disagree historically.
- "Backend green but frontend red" is NOT green. All workflows must be green.
- Never leave a failing workflow running — disable it. A red workflow trains everyone to ignore CI.

---

## 2. Infrastructure patterns that worked

### Dockerfile — multi-stage build
```dockerfile
FROM python:3.12-slim AS base     # shared deps
FROM base AS test                  # + pytest, ruff → run tests at build time
FROM base AS prod                  # clean image, no test deps
```
- Test stage is built first; if pytest fails, the whole build fails.
- Prod stage reuses base layers via Docker cache — building both is barely slower than one.
- Production image stays lean: no tests/, no pytest, no ruff.

### Cloud Build with async polling
- `gcloud builds submit --async` + manual polling instead of letting gcloud block on log streaming.
- Reason: service accounts without project-wide log viewer permission cause `gcloud builds submit` to exit non-zero even on successful builds, which trips `set -e`.
- Poll with `gcloud builds describe $BUILD_ID --format="value(status)"` every 10s.
- Cap at 15 minutes. Handle all terminal states: SUCCESS, FAILURE, INTERNAL_ERROR, TIMEOUT, CANCELLED, EXPIRED.

### Deploy script safety
- deploy-dev.sh auto-bumps VERSION. deploy-prod.sh does NOT bump — it promotes whatever DEV produced.
- VERSION format: `MAJOR.NNN` (e.g., `3.042`). Strict regex validation in both scripts. Rejects old formats.
- deploy-prod.sh prints the proposed git tag and exact commands but never creates it.
- PROD deploy sets `--min-instances=1` and `--no-cpu-throttling` to prevent cold-start latency.
- PROD deploy includes `gcloud run services update` to ensure resource limits are correct (2 CPU, 2GB RAM).
- deploy-prod.sh auto-rollback: `_AUTO_ROLLBACK=true` in Cloud Build triggers automatic traffic shift back to previous revision if smoke tests fail.

### Environment-prefixed Firestore collections
- Pattern: `dev_users`, `prod_users`, `dev_audit_log`, `prod_audit_log`.
- Same Firestore database, different collection prefixes per environment.
- Simple, works well, no cross-environment data leakage risk.

### Cloud Run service naming
- Pattern: `{project}-api-{env}` (e.g., `masteko-dwh-api-dev`, `masteko-dwh-api-prod`).
- Both DEV and PROD share the same Cloud Run URL hash — watch out for copy-paste errors.
- Always use the primary URL format consistently.

### Firebase Hosting with /api rewrites
- Firebase Hosting rewrites `/api/**` to the Cloud Run service.
- Separate hosting targets: `dev` → `dev-{app}`, `prod` → `{app}`.
- SPA fallback: `** → /index.html` for React Router.

### Secret Manager — everything
- QBO keys, Google OAuth, encryption keys, admin emails — ALL in Secret Manager.
- Never env vars for secrets. `.env` files for local dev only, gitignored.
- Service account needs `roles/secretmanager.secretAccessor`.

---

## 3. Auth patterns

### DEV auth bypass
- `DEV_AUTH_BYPASS=true` env var enables token bypass in DEV Cloud Run.
- Dev tokens format: `dev-{email}` which maps to real Firebase UIDs via Firestore email lookup.
- PROD must NEVER set `DEV_AUTH_BYPASS=true`.
- Auth middleware checks this flag — same middleware handles both paths.

### Firestore security rules — deny-all with Admin SDK
- Default: deny everything from client. Backend uses Admin SDK (bypasses rules).
- Explicit deny for audit log — even restating the catch-all, for intent clarity.
- Rules are defense-in-depth, not primary enforcement. Backend is source of truth.
- If you add Firestore real-time listeners (onSnapshot) from frontend, you'll need to open specific read paths.

### RBAC lessons
- Every API endpoint must have explicit auth decoration. No endpoint goes live without a category.
- UI hiding is NOT enforcement. Backend is always the source of truth.
- Last-admin protection is mandatory — system must always have at least one admin.
- Firebase Auth tokens and Cloud Tasks OIDC tokens are separate auth paths — never accept one where the other is expected.
- Legacy user docs without `role` field need auto-upgrade logic (safe default = viewer).
- `display_name=None` from Firebase can break Pydantic strict mode — coerce None→"" in `from_firestore`.

---

## 4. Gotchas that broke things

### Python version
- Python 3.14 is incompatible with gRPC. Use Python 3.12.
- README once claimed 3.14 while everything ran on 3.12. Documentation freshness policy was created because of this.

### Ruff lint config divergence
- GitHub Actions and Cloud Build had different `--ignore` flags, causing lint to pass in one and fail in the other.
- Fix: single source of truth in `pyproject.toml`. CI files invoke ruff with minimum flags, never `--select` or `--ignore`.

### NPM peer dependency conflicts
- `@tailwindcss/vite` had a peer dependency conflict with `vite@8.0.0` that broke `npm ci` in CI.
- CI uses `npm ci` (clean install) which is stricter than `npm install`.

### Stale documentation
- Test count drifted across three documents (169 / 213 / 221) without anyone noticing.
- Entity count and deploy mechanism described in README didn't match reality.
- Fix: Documentation Freshness Policy — four watched documents with trigger lists and "Last reviewed" markers.

### Stuck ETL runs blocking the UI
- ETL runs and API serving share the same Cloud Run instance.
- Heavy ETL saturates CPU, health checks time out, dashboard becomes unresponsive.
- Recommendation for MastekoFM: separate compute-heavy work (spreadsheet calculation) from API serving.

### Cloud Tasks OIDC
- Cloud Tasks sends OIDC tokens to internal endpoints. Must verify them.
- Internal endpoints should not accept Firebase user tokens — prevents privilege escalation via token confusion.

### Firestore composite indexes
- Queries on `realm_id + started_at` and `realm_id + status + started_at` needed composite indexes.
- If a Firestore query fails with an index error, the error message includes a direct link to create the index.

### Attachment dedup
- Original: per-file API call to check if file exists (614 calls for 614 attachments).
- Fixed: single `list_files_in_folder()` call, check in memory.
- Lesson: batch API calls wherever possible, especially for Google Drive/Sheets.

### Google Sheets API batching
- Original: 30 API calls to create tabs and write data.
- Fixed: batch tab creation + batch data write → 3 API calls.
- Same lesson: batch everything.

---

## 5. Process patterns worth carrying forward

### Epic discipline
- Every non-trivial feature gets an epic file in `docs/epics/`.
- One branch per epic: `epic/{epic-id}-{short-name}`.
- One commit per story (not per file) — `git revert <sha>` rolls back a whole story.
- Epic branches deploy to DEV freely, NEVER to PROD. PROD only from main.
- Merge with `--no-ff` so the merge commit is a clean revert boundary.
- An epic is not "done" until every story is validated live on DEV. Unit tests are necessary but not sufficient.

### Continuous standards refinement ("fix as you find")
- When you find a bug, contradiction, or missing rule while doing other work, fix it in the same commit.
- Don't defer small fixes. The pile-up of deferred fixes is how you get 92 lint errors and 5 stale documents.
- But apply judgment: if the fix would double the commit size or touch unrelated subsystems, open a backlog item instead.

### T-shirt sizing
- XS (<2h), S (half day), M (1–2 days), L (3–4 days), XL (1 week+).
- An epic containing an XL story should be split before starting.
- Story effort includes validation time, not just coding time.

### Standing authorizations (DEV vs PROD asymmetry)
- DEV is recoverable. Claude can deploy, break, fix, iterate freely on DEV.
- PROD is not recoverable. Every PROD action requires explicit per-action approval.
- The cost of asking for DEV approval is high (breaks flow). The cost of a DEV mistake is low (re-deploy).
- The cost of asking for PROD approval is low (5 seconds). The cost of a PROD mistake is high (data loss, downtime).

### Post-deploy rollback
- Rollback must be a sub-60-second operation.
- Practice rollback quarterly or after any CI/CD change.
- MastekoDWH measured: 14s rollback + 11s roll-forward in DEV.

### Version format
- `MAJOR.NNN` — exactly one dot, zero-padded 3-digit counter.
- Auto-bumped on DEV deploy. PROD promotes whatever DEV produced (no independent bump).
- Git SHA captured separately via Cloud Build substitution, surfaced via `/api/version`.

---

## 6. Lessons learned in MastekoFM (2026-04, Excel Template MVP)

### Fastly strips `X-Google-*` headers ⚡
Firebase Hosting fronts Cloud Run via Fastly. Fastly silently strips any HTTP header matching `X-Google-*` because Google reserves that prefix for internal edge signaling. We learned this when our `X-Google-Access-Token` header (used to pass the user's Google OAuth token to the backend for Drive API calls) appeared at the browser side but was missing in the FastAPI request.headers dict.

**Fix**: rename to `X-MFM-Drive-Token` (or any non-`X-Google-*` name). Bug found in v1.030, fixed in v1.032.

**Diagnosis tip**: when a custom header "disappears" between browser and backend, write a temporary diagnostic endpoint that dumps `request.headers.keys()` and call it directly. Compare to the `fetch` call's headers in DevTools.

### Stale bundle after deploy ⚡
By default Firebase Hosting caches `index.html` aggressively, while Vite-hashed JS bundles in `/assets/` change filename per build. Result: a user with a cached `index.html` keeps loading the old JS hash forever, never seeing your deploys.

**Fix**: in `firebase.json`, add `Cache-Control: no-cache, no-store, must-revalidate` on `/index.html` and `Cache-Control: public, max-age=31536000, immutable` on `/assets/**`. Bug fixed in v1.034.

### Firebase token race on initial render ⚡
React component's initial `useEffect` may fire before Firebase's `onAuthStateChanged` callback sets the token. Components fire API requests with no Authorization header → 401.

**Fix**: have the API client poll for the token (up to 3s) before issuing each request. Or pass `token` as a `useEffect` dependency so the effect re-runs when it arrives. Both implemented in v1.033 (`api.ts`).

### Google account switching is awkward ⚡
When a user has multiple Google accounts in Chrome, hitting a project that one account doesn't have access to leads to a confusing "project does not exist" page. The browser doesn't auto-prompt account chooser.

**Fix**: use `?authuser=N` URL param to force account index. Better: documented in OAuth setup that the right Google account must be the default in Chrome before clicking app links.

### OAuth consent screen verification not needed for `drive.file` scope
The `https://www.googleapis.com/auth/drive.file` scope is **non-sensitive** — Google does not require app verification for it. Apps can be published in Production mode immediately, accessible to any Google account, no test-user list. We learned this is the right scope choice for a Drive-integrated app: it lets MastekoFM read/write only the files it creates or the user explicitly opens, never a user's whole Drive.

**Avoid**: `auth/drive` (full Drive scope) — it's restricted, requires verification, and overreaches.

### Office Editing mode in Sheets is the right UX
A `.xlsx` file in Drive opens in Google Sheets in "Office Compatibility Mode" — file format stays `.xlsx` (no conversion), but the user gets the Sheets editing experience. Saves write back as `.xlsx`. Best of both worlds: portable file format + browser editing + shareable + version history.

URL pattern: `https://docs.google.com/spreadsheets/d/{drive_file_id}/edit` — opens in Office mode automatically when the file is `.xlsx`.

This eliminates the need for a custom in-browser spreadsheet editor (Luckysheet, Univer, etc.) for the v1 of MastekoFM.

### LibreOffice double-conversion forces recalc ⚡
When you open an `.xlsx` in LibreOffice headless and "convert" it back to `.xlsx`, formulas don't always recalculate. Workaround: convert `.xlsx → .ods → .xlsx` — going through ODS forces a full reparse and recalc.

```bash
soffice --headless --calc --convert-to ods input.xlsx
soffice --headless --calc --convert-to xlsx input.ods
```

Adds ~2-3 seconds per file vs single-pass. Acceptable. Implemented in `excel_engine.recalculate_with_libreoffice`.

### MergedCells are read-only in openpyxl ⚡
Trying to set `.value` on a `MergedCell` raises `AttributeError`. To overlay onto a destination tab that has merged ranges, you MUST unmerge first, then write, then re-merge from the source. The engine's `overlay_tab` does exactly this. Proven on Campus Adele which has many merged header cells.

### Tab prefixes must be case-sensitive ⚡
Campus Adele's "Construction-to-Perm" model has both `I_Inputs & Assumptions` (real input tab) and `i_Cap Table` (calc tab — lowercase `i_`). If we did case-insensitive prefix matching, we'd silently treat `i_Cap Table` as an input and overlay over it, breaking the Cap Table calculations.

**Rule**: validators MUST use `str.startswith("I_")` literally. Never `.lower()`.

### Cloud Tasks delivers same task twice ⚡ (pre-emptive lesson, not yet hit)
At-least-once delivery is a Cloud Tasks guarantee. Workers MUST be idempotent: check Run.status at the start of handler. If `running` (and recently started), assume another worker has it; skip. If `completed`/`failed`, ack the task and return.

### Don't auto-commit, ever
Same lesson as MastekoDWH. CLAUDE.md restates this. Even when an agent is in flow and "knows" the commit is good — the human reviews. Saved us from at least two wrong commits during the Sprint A planning session.

### Sync calculation blocks Cloud Run too long
Campus Adele takes ~17s synchronously. Cloud Run's request timeout default is 60s but the user's browser is staring at a spinner the whole time. For one user it's tolerable. For 100 concurrent users it's catastrophic. Sprint C async is non-optional once we have real traffic.

### Test with the REAL fixture, not synthetic
Our 18 engine tests use the actual Campus Adele `.xlsx` (476 KB, 15 tabs, 13,000+ formulas). Synthetic tests would have missed the MergedCell issue, the case-sensitive prefix issue, and the cross-tab formula behavior. Real fixtures are gold.

---

## 7. Sprint B / Sprint A.5 / INFRA-001 (2026-04-25)

### Bulk renames need test runs after EACH replacement step ⚡
A 17-replacement bulk script that ran in one shot caused 4 separate compile errors:
1. `class Scenario` → `class AssumptionPack` plus `ScenarioRunResponse` → `PackRunResponse` ran in same pass, producing `class AssumptionAssumptionPackRunResponse` (double substitution)
2. `ScenarioStore` Protocol class became `AssumptionPackStore`, but type annotations on `_STORES` dict + `get_store()` and `store_for_scenario()` returns still said `ScenarioStore`
3. Internal collection refs `f"{prefix}excel_templates"` weren't all caught by the script's pattern matching
4. The `backend/app/connectors/` directory wasn't in my delete list — Cloud Build caught it with a ruff failure

**Lesson**: after any bulk rename touching N files, run `pytest && ruff check` BEFORE committing. The cost of running tests is seconds; the cost of a failed Cloud Build is minutes.

### Don't forget hidden subdirectories on bulk delete ⚡
`rm -v <list>` only removes files explicitly listed. Subdirectories importing deleted modules (like `backend/app/connectors/`) silently survive. Whenever you delete a category of code, do `find . -name "__init__.py" | xargs grep -l "from backend.app.models.deleted_module"` to catch stragglers.

### Cloud Build's test stage is the safety net ⚡
Cloud Run deploy = Cloud Build = `Dockerfile`'s test stage = `ruff check` + `pytest`. If local tests pass but Cloud Build fails, it's almost always: a file you forgot existed, a dependency mismatch between local venv and `backend/requirements.txt`, or a path that's case-sensitive on Linux but not Mac. Trust the test stage.

### `Path(__file__).resolve().parents[N]` breaks in containers if you forget to COPY directories ⚡
`backend/app/routers/seed.py` calculates `REPO_ROOT = Path(__file__).resolve().parents[3]` to find `seed/`. This works on dev but fails in Docker if `COPY seed/` is missing from the Dockerfile. The error is "Seed file missing: /app/seed/helloworld/...". Always COPY all dirs the runtime needs, not just `backend/app/`.

### Workload Identity Federation > service account JSON keys ⚡
For GitHub Actions ↔ GCP, WIF means zero long-lived secrets. The setup is one shell script (Service Account + IAM bindings + Workload Identity Pool + Provider + Repo binding), one set of GitHub repository variables (no secrets), and `google-github-actions/auth@v2` in the workflow. Done.

Firebase Hosting still needs a service account JSON because Firebase doesn't fully support WIF for hosting deploys yet. That's one secret in GitHub Actions. Acceptable.

### LibreOffice in CI matters ⚡
Local pytest skips engine tests if LibreOffice isn't present. Cloud Build runs the test stage with `libreoffice-calc-nogui` installed, so engine tests run. GitHub Actions CI must also `apt-get install libreoffice-calc-nogui` BEFORE `pytest` or the engine tests just silently skip. They've caught two real bugs in the engine — don't lose them in CI.

### A "thin org scope" entity is a useful pattern ⚡
Sprint B refactor: `Project` was bound 1:1 to a Model (rigid). The redesign made `Project` a thin org scope: members, Drive folder, optional `default_model_id` for UX convenience. AssumptionPacks belong to Projects, but Models and OutputTemplates float free at workspace level. This separation made the three-way composition (Project + Pack + Model + OutputTemplate) much cleaner.

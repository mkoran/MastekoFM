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

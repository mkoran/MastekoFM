# Sprint INFRA-002 — End-to-end smoke (seed → run → assert Sum=12)

> Status: ✅ shipped (script + workflow integration). Activates fully in CI
> once Marc adds the deployer SA as Editor on the Drive root folder.
> Branch: `epic/sprint-b-cleanup` (continued)

## Why

Pre-Sprint-UX-01, two production bugs (Create Pack 500, Calculate no-op)
shipped to DEV because the existing post-deploy smoke (`curl /health`) only
verified that the container started — it did not exercise the engine. Both
bugs would have been caught immediately by a script that hit the real seed
endpoint, kicked off a real Run, and asserted the expected output cells.

This sprint closes that gap.

## What it does

`scripts/smoke/e2e_run_smoke.py`:

1. `POST /api/seed/helloworld` (idempotent — re-running returns the existing ids)
2. `POST /api/runs` with the returned `(project_id, model_id, pack_id, tpl_id)`
3. Polls `GET /api/runs/{id}` until terminal (zero-poll for sync; ready for Sprint C async)
4. Downloads `output_download_url`
5. Opens the .xlsx with openpyxl, asserts `O_Report!B3 == 12`, `B4 == 35`, `B5 == 47`

The script is stdlib-only for HTTP (urllib) so it has no extra runtime deps
beyond what the Hello World engine already needs (`openpyxl`, `google-auth`).

## Auth model

| Token | Header | How CI gets it |
|---|---|---|
| API token | `Authorization: Bearer ...` | DEV: `dev-ci-smoke@example.com` (DEV_AUTH_BYPASS). PROD: skipped (needs real Firebase auth — separate sprint). |
| Drive token | `X-MFM-Drive-Token: ya29...` | DEV: minted from WIF SA via `google.auth.default(scopes=["drive.file"])` then `creds.refresh()`. Locally: `MFM_DRIVE_TOKEN` env var. |

### Marc's one-time setup to activate the CI E2E

Once you've activated WIF (`./scripts/infra/setup_github_wif.sh`), the deployer
service account email looks like
`mfm-github-deployer@masteko-fm.iam.gserviceaccount.com`. To let it act on
your Drive root folder:

1. In Drive, open the folder configured in `/api/settings → drive_root_folder_id`
2. Share → add `mfm-github-deployer@masteko-fm.iam.gserviceaccount.com` as **Editor**
3. Done. The next CI deploy will exercise the full engine path.

If you haven't activated WIF yet, the e2e step in `deploy-dev.yml` will fail
fast (--required), making it visible that CI still needs setup.

## Local usage

```bash
# Manual run after a local deploy:
export API_BASE_URL=$(gcloud run services describe masteko-fm-api-dev \
    --project=masteko-fm --region=northamerica-northeast1 --format='value(status.url)')
export AUTH_TOKEN="dev-cli-smoke@example.com"

# Get a Drive token from your active session:
#   - From the running app: open devtools → Network → grab X-MFM-Drive-Token from any request
#   - Or use ADC if you've run `gcloud auth application-default login --scopes=...,https://www.googleapis.com/auth/drive.file`
export MFM_DRIVE_TOKEN="ya29.A0..."

python scripts/smoke/e2e_run_smoke.py --required
```

`deploy-dev.sh` calls the script automatically after the bash smoke; without
a token it SKIPS gracefully (no deploy failure). In CI it uses `--required`
so missing creds fails the deploy.

## Stories

| ID | Story | Status |
|---|---|---|
| INFRA-002-01 | Python e2e smoke script (stdlib HTTP, openpyxl assertion) | ✅ |
| INFRA-002-02 | Wire into `deploy-dev.sh` (graceful skip without token) | ✅ |
| INFRA-002-03 | Wire into `.github/workflows/deploy-dev.yml` (`--required`, mints SA token) | ✅ |
| INFRA-002-04 | pytest covering script's branching (skip / fail / pass / poll) | ✅ |
| INFRA-002-05 | Docs: this file | ✅ |
| INFRA-002-06 | Marc's one-time Drive folder share (deferred — outside Claude's scope) | 🔒 |

## Test count delta
- Before: **81/81**
- After: **88/88** (+7 in `tests/test_e2e_smoke_script.py`)

## What this catches that the bash smoke didn't

| Bug class | bash smoke | e2e smoke |
|---|---|---|
| Container failed to start | ✅ | ✅ |
| Health endpoint broken | ✅ | ✅ |
| Auth gate broken | ✅ | ✅ |
| Frontend bundle stale / missing | ✅ | ✅ |
| Seed endpoint broken | ❌ | ✅ |
| **Create AssumptionPack 500 (UX-01-01)** | ❌ | ✅ |
| **Calculate no-op (UX-01-02)** | ❌ | ✅ |
| Engine LibreOffice subprocess broken | ❌ | ✅ |
| Output cell values wrong (math regression) | ❌ | ✅ |
| Drive integration broken | ❌ | ✅ |

## Future work

- **PROD smoke** — needs real Firebase Auth. One option: a CI Firebase user
  with custom-token minting via Firebase Admin SDK using the WIF SA. Defer.
- **Cell-level assertions on Campus Adele** — the 7,302-formula model is the
  real engine torture test. Pinning even one cell value would catch a much
  wider class of engine regressions. ~30 min once we know which cell.

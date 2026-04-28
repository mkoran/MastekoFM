# Sprint INFRA-001 — CI/CD via GitHub Actions + Workload Identity Federation

> Status: scaffolding committed. Marc completes setup steps below to activate.
> Branch: `epic/sprint-b-cleanup` (rolled in alongside Sprint B since the workflows live in `.github/workflows/`)

---

## Goal

Eliminate the `firebase login --reauth` / `gcloud auth login` dance. Every push to `epic/*` auto-deploys to DEV. Every PR gets a Firebase Hosting preview URL. PRs require CI green to merge. PROD deploy is a button-click in GitHub Actions with manual approval.

**No long-lived service account keys** stored in GitHub for GCP — auth via Workload Identity Federation (short-lived OIDC tokens minted by GitHub Actions). Firebase Hosting still needs a SA JSON (one secret) because Firebase doesn't fully support WIF yet for hosting deploys.

---

## What was built

| File | Purpose |
|---|---|
| `scripts/infra/setup_github_wif.sh` | One-shot setup: creates `mfm-deployer` SA, IAM bindings, Workload Identity Pool + Provider, repo binding |
| `.github/workflows/ci.yml` | On push to main / epic/*, runs `pytest` + `ruff` + `npm run build`. Required check on PRs. (Updated to install LibreOffice for engine tests.) |
| `.github/workflows/deploy-dev.yml` | On push to `epic/*`, bumps VERSION, builds backend via Cloud Build, deploys frontend to Firebase Hosting, runs smoke tests, commits VERSION bump back |
| `.github/workflows/deploy-prod.yml` | Manual `workflow_dispatch` OR push of a `prod-v*` tag. Requires GitHub Environment "production" approval. Uses `_AUTO_ROLLBACK=true` Cloud Build substitution. |
| `.github/workflows/pr-preview.yml` | Every PR gets a 7-day Firebase Hosting preview channel |

---

## Setup steps (one-time, ~15 minutes)

### Step 1. Run the WIF setup script

```bash
cd "/path/to/MastekoFM"
./scripts/infra/setup_github_wif.sh
```

Auth as a user with **Owner** or **IAM Admin** on `masteko-fm`. The script prints values you'll need next.

### Step 2. Add GitHub Actions repository variables

Go to https://github.com/mkoran/MastekoFM/settings/variables/actions → **Variables tab → New repository variable**:

| Name | Value |
|---|---|
| `GCP_PROJECT_ID` | `masteko-fm` |
| `GCP_REGION` | `northamerica-northeast1` |
| `GCP_WIF_PROVIDER` | `projects/<NUMBER>/locations/global/workloadIdentityPools/github-actions/providers/github` (printed by the script) |
| `GCP_DEPLOYER_SA_EMAIL` | `mfm-deployer@masteko-fm.iam.gserviceaccount.com` |
| `GCP_BACKEND_SERVICE` | `masteko-fm-api-dev` |
| `FIREBASE_HOSTING_TARGET` | `dev` |

### Step 3. Add GitHub Actions secret for Firebase Hosting

Firebase Hosting still needs a separate service account JSON. Generate one:

```bash
gcloud iam service-accounts keys create /tmp/firebase-deployer-key.json \
  --iam-account=mfm-deployer@masteko-fm.iam.gserviceaccount.com
cat /tmp/firebase-deployer-key.json
rm /tmp/firebase-deployer-key.json
```

Then go to https://github.com/mkoran/MastekoFM/settings/secrets/actions → **New repository secret**:

| Name | Value |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | (paste the entire JSON contents from above) |

**Delete the local key file immediately** — the JSON is in GitHub now, never commit it.

### Step 4. Set up the production GitHub Environment

For PROD deploys to require manual approval:

1. https://github.com/mkoran/MastekoFM/settings/environments → **New environment** → name: `production`
2. ✅ **Required reviewers** → add yourself
3. Save

Now `deploy-prod.yml` waits for your "Approve" click in the GitHub Actions UI before running.

### Step 5. Branch protection for main (optional but recommended)

Settings → Branches → **Add rule** for `main`:
- ✅ Require status checks to pass before merging
  - Required checks: `backend`, `frontend` (from `ci.yml`)
- ✅ Require pull request reviews before merging (1 reviewer — you can dismiss your own if needed)
- ✅ Require linear history
- ❌ Allow force pushes — never

---

## Day-to-day flow after setup

| Action | What happens |
|---|---|
| Push to `epic/sprint-c-async` | `ci.yml` runs (~3 min). If green, `deploy-dev.yml` runs (~5 min). DEV updates automatically. VERSION auto-bumped + committed back. |
| Open a PR to `main` | `ci.yml` runs, `pr-preview.yml` posts an ephemeral 7-day Hosting URL in the PR comments. |
| Merge PR to `main` | `ci.yml` runs on main. (No auto-deploy to PROD — explicit step) |
| Manual dispatch of `deploy-prod.yml`, OR `git tag prod-v2.012 && git push --tags` | Workflow runs after manual approval in GitHub Actions UI. Cloud Run rolls out, auto-rollback on smoke-test failure. |

No more `gcloud auth login` for routine work. The local `deploy-dev.sh` / `deploy-prod.sh` stay around as escape hatches.

---

## What's NOT in this sprint

- Cloud Tasks worker auth (Sprint C will add a separate identity for the worker service)
- Per-PR ephemeral backend (just frontend previews for now — backend stays as DEV Cloud Run)
- Slack/email notifications on deploy success/failure
- Production rollback button in UI (manual `gcloud run services update-traffic` for now, but `_AUTO_ROLLBACK=true` in Cloud Build handles smoke-test failures)

---

## Verification

After the setup steps:
1. Push any commit to `epic/sprint-b-cleanup` (or any `epic/*` branch)
2. Watch the Actions tab on GitHub
3. Within ~7 minutes, https://dev-masteko-fm.web.app should show the new VERSION

If it works once end-to-end, you're done — every future push deploys automatically.

---

## Why Workload Identity Federation, not a service account JSON for GCP?

Long-lived service account keys are credentials. If a key leaks (committed to GitHub, accidentally posted in chat, etc.), an attacker has indefinite access. WIF instead:

1. GitHub Actions calls `https://token.actions.githubusercontent.com` for an OIDC token (signed by GitHub, claims include repo + branch)
2. Google IAM verifies the OIDC signature + checks the claim against the binding (`repository == 'mkoran/MastekoFM'`)
3. If valid, Google issues a short-lived (1 hour) access token for the deployer SA
4. The Action uses that token; it expires automatically

Net: zero long-lived secrets stored anywhere. Repo gets compromised? Attacker still can't deploy unless they're running inside an actual GitHub Actions job for our specific repo.

This is the [official Google recommendation for GitHub Actions ↔ GCP](https://github.com/google-github-actions/auth#workload-identity-federation).

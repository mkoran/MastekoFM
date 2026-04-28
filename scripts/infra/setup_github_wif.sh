#!/usr/bin/env bash
# Sprint INFRA-001 — One-shot setup for GitHub Actions ↔ GCP via Workload Identity Federation.
#
# Run this ONCE per project. Re-running is mostly idempotent (resources skipped if they exist).
#
# Prereqs:
#   - gcloud CLI authenticated as a user with Owner / IAM Admin on masteko-fm
#   - GitHub repo: github.com/mkoran/MastekoFM
#
# What it creates:
#   1. Service account: mfm-deployer@masteko-fm.iam.gserviceaccount.com
#   2. IAM bindings: Cloud Run Admin, Cloud Build Editor, Storage Admin,
#      Firestore User, Firebase Hosting Admin, Service Account User
#   3. Workload Identity Pool: github-actions
#   4. Workload Identity Provider: github (OIDC issuer = token.actions.githubusercontent.com)
#   5. IAM binding allowing the GitHub repo to impersonate the deployer SA
#
# After this script, GitHub Actions can deploy without any long-lived secrets.

set -euo pipefail

PROJECT_ID="masteko-fm"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA_NAME="mfm-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_ID="github-actions"
PROVIDER_ID="github"
GITHUB_REPO="mkoran/MastekoFM"
REGION="northamerica-northeast1"

echo "Project: $PROJECT_ID (number: $PROJECT_NUMBER)"
echo "Repo:    $GITHUB_REPO"
echo

# ── 1. Service account ─────────────────────────────────────────────────────────
echo "[1/5] Creating deployer service account..."
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="MastekoFM GitHub Actions deployer" \
  --description="Used by GitHub Actions to deploy to Cloud Run + Firebase Hosting. Impersonated via Workload Identity Federation." \
  || echo "  (service account already exists, skipping)"

# ── 2. IAM bindings ────────────────────────────────────────────────────────────
echo "[2/5] Granting IAM roles..."
ROLES=(
  "roles/run.admin"
  "roles/cloudbuild.builds.editor"
  "roles/storage.admin"
  "roles/datastore.user"
  "roles/firebasehosting.admin"
  "roles/iam.serviceAccountUser"
  "roles/artifactregistry.writer"
  "roles/secretmanager.secretAccessor"
)
for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" \
    --condition=None \
    --quiet > /dev/null
  echo "  granted $role"
done

# Cloud Build needs to act as the Compute Engine default SA to deploy to Cloud Run
gcloud iam service-accounts add-iam-policy-binding \
  "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet > /dev/null
echo "  granted serviceAccountUser on Compute Engine default SA"

# ── 3. Workload Identity Pool ──────────────────────────────────────────────────
echo "[3/5] Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions" \
  || echo "  (pool already exists, skipping)"

POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"

# ── 4. OIDC Provider for GitHub ────────────────────────────────────────────────
echo "[4/5] Creating OIDC provider for GitHub..."
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  || echo "  (provider already exists, skipping)"

PROVIDER_RESOURCE="${POOL_RESOURCE}/providers/${PROVIDER_ID}"

# ── 5. Allow the repo to impersonate the SA ────────────────────────────────────
echo "[5/5] Binding GitHub repo to service account..."
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPO}" \
  --quiet > /dev/null

echo
echo "✅ Setup complete."
echo
echo "Add these as GitHub Actions repository variables (Settings → Secrets and variables → Actions → Variables):"
echo
echo "  GCP_PROJECT_ID         = ${PROJECT_ID}"
echo "  GCP_REGION             = ${REGION}"
echo "  GCP_WIF_PROVIDER       = ${PROVIDER_RESOURCE}"
echo "  GCP_DEPLOYER_SA_EMAIL  = ${SA_EMAIL}"
echo "  GCP_BACKEND_SERVICE    = masteko-fm-api-dev   (for the dev workflow)"
echo "  FIREBASE_HOSTING_TARGET= dev"
echo
echo "(No long-lived secrets. Firebase Hosting uses Application Default"
echo " Credentials from the WIF auth step.)"
echo
echo "Then push to a branch and the deploy-dev workflow will run automatically."

# Print the gh CLI commands to set the variables (so a follow-up automation
# can apply them without manual GitHub UI clicks):
cat <<EOF

If you have gh CLI authenticated with repo scope, run these to set the
GitHub repository variables:

  gh variable set GCP_PROJECT_ID --repo "${GITHUB_REPO}" --body "${PROJECT_ID}"
  gh variable set GCP_REGION --repo "${GITHUB_REPO}" --body "${REGION}"
  gh variable set GCP_WIF_PROVIDER --repo "${GITHUB_REPO}" --body "${PROVIDER_RESOURCE}"
  gh variable set GCP_DEPLOYER_SA_EMAIL --repo "${GITHUB_REPO}" --body "${SA_EMAIL}"
  gh variable set GCP_BACKEND_SERVICE --repo "${GITHUB_REPO}" --body "masteko-fm-api-dev"
  gh variable set FIREBASE_HOSTING_TARGET --repo "${GITHUB_REPO}" --body "dev"
EOF

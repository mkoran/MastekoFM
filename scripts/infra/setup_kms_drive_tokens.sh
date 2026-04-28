#!/usr/bin/env bash
# Sprint F — one-time per-env setup of the KMS keyring used to encrypt
# Drive OAuth tokens persisted on Run docs.
#
# What this does (idempotent):
#   1. Enables cloudkms.googleapis.com
#   2. Creates keyring   mfm-secrets-{env}    in northamerica-northeast1
#   3. Creates key       drive-tokens         (rotation: 90 days)
#   4. Grants the API runtime SA cloudkms.cryptoKeyEncrypterDecrypter
#
# Usage:
#   ./scripts/infra/setup_kms_drive_tokens.sh dev
#   ./scripts/infra/setup_kms_drive_tokens.sh prod
#
# After this runs, services/secrets.py's is_kms_available() returns True on
# the deployed service and the runs router will encrypt Drive tokens before
# persisting them to Firestore.
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
    echo "Usage: $0 <dev|prod>"
    exit 1
fi

PROJECT_ID="masteko-fm"
REGION="northamerica-northeast1"
KEYRING_NAME="mfm-secrets-${ENV}"
KEY_NAME="drive-tokens"
SERVICE_NAME="masteko-fm-api-${ENV}"

echo "── Sprint F KMS setup for env=${ENV} ──────────────────────────"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Keyring: $KEYRING_NAME"
echo "  Key:     $KEY_NAME"
echo

# 1. Enable Cloud KMS API (no-op if enabled)
echo "1) Enable cloudkms.googleapis.com…"
gcloud services enable cloudkms.googleapis.com --project="$PROJECT_ID"

# 2. Create keyring (idempotent)
echo "2) Create keyring $KEYRING_NAME…"
if gcloud kms keyrings describe "$KEYRING_NAME" \
        --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "   keyring already exists"
else
    gcloud kms keyrings create "$KEYRING_NAME" \
        --location="$REGION" --project="$PROJECT_ID"
fi

# 3. Create key with 90-day rotation (idempotent)
echo "3) Create key $KEY_NAME (90d rotation)…"
if gcloud kms keys describe "$KEY_NAME" \
        --location="$REGION" --keyring="$KEYRING_NAME" \
        --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "   key already exists"
else
    gcloud kms keys create "$KEY_NAME" \
        --location="$REGION" \
        --keyring="$KEYRING_NAME" \
        --project="$PROJECT_ID" \
        --purpose=encryption \
        --rotation-period=90d \
        --next-rotation-time="$(date -u -v+90d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '+90 days' +%Y-%m-%dT%H:%M:%SZ)"
fi

# 4. Grant the API runtime SA encrypt/decrypt
RUNTIME_SA=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" --region="$REGION" \
    --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)
if [[ -z "$RUNTIME_SA" ]]; then
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi
echo "4) Grant $RUNTIME_SA cryptoKeyEncrypterDecrypter on the key…"
gcloud kms keys add-iam-policy-binding "$KEY_NAME" \
    --location="$REGION" \
    --keyring="$KEYRING_NAME" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" >/dev/null

echo
echo "✅ KMS ready for env=${ENV}."
echo "   On the next deploy, services/secrets.py:is_kms_available() will return True"
echo "   and POST /api/runs will encrypt the Drive token before persisting."
echo
echo "Verify with:"
echo "   gcloud kms keys describe $KEY_NAME --location=$REGION --keyring=$KEYRING_NAME --project=$PROJECT_ID"

#!/usr/bin/env bash
# Sprint C — one-time per-env setup of the Cloud Tasks runs queue.
#
# What this does (idempotent — re-runnable):
#   1. Enables cloudtasks.googleapis.com (no-op if already enabled)
#   2. Creates queue mfm-runs-{env} (no-op if already exists)
#   3. Creates SA mfm-runs-worker@... (used by Cloud Tasks for OIDC)
#   4. Grants the SA roles/run.invoker on the API service
#   5. Updates the Cloud Run service env vars: RUNS_QUEUE, RUNS_WORKER_URL,
#      RUNS_WORKER_SA — flipping the API from sync-thread mode to Cloud Tasks mode
#
# Usage:
#   ./scripts/infra/setup_runs_queue.sh dev     # sets up DEV
#   ./scripts/infra/setup_runs_queue.sh prod    # sets up PROD
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
    echo "Usage: $0 <dev|prod>"
    exit 1
fi

PROJECT_ID="masteko-fm"
REGION="northamerica-northeast1"
QUEUE_NAME="mfm-runs-${ENV}"
SERVICE_NAME="masteko-fm-api-${ENV}"
WORKER_SA_NAME="mfm-runs-worker"
WORKER_SA_EMAIL="${WORKER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "── Sprint C runs-queue setup for env=${ENV} ─────────────────────"
echo "  Project:    $PROJECT_ID"
echo "  Region:     $REGION"
echo "  Queue:      $QUEUE_NAME"
echo "  API svc:    $SERVICE_NAME"
echo "  Worker SA:  $WORKER_SA_EMAIL"
echo

# 1. Enable Cloud Tasks API
echo "1) Enable Cloud Tasks API…"
gcloud services enable cloudtasks.googleapis.com --project="$PROJECT_ID"

# 2. Create the queue (idempotent)
echo "2) Create queue $QUEUE_NAME (idempotent)…"
if gcloud tasks queues describe "$QUEUE_NAME" \
        --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "   queue already exists"
else
    gcloud tasks queues create "$QUEUE_NAME" \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --max-concurrent-dispatches=10 \
        --max-attempts=3 \
        --min-backoff=10s \
        --max-backoff=300s
fi

# 3. Create the worker service account (idempotent)
echo "3) Create SA $WORKER_SA_EMAIL (idempotent)…"
if gcloud iam service-accounts describe "$WORKER_SA_EMAIL" \
        --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "   SA already exists"
else
    gcloud iam service-accounts create "$WORKER_SA_NAME" \
        --display-name="MastekoFM runs worker (Cloud Tasks OIDC)" \
        --project="$PROJECT_ID"
fi

# 4. Grant run.invoker on the API service so Cloud Tasks can call /internal/tasks/*
echo "4) Grant roles/run.invoker on $SERVICE_NAME to $WORKER_SA_EMAIL…"
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --member="serviceAccount:${WORKER_SA_EMAIL}" \
    --role="roles/run.invoker" >/dev/null
echo "   binding applied"

# 5. Update Cloud Run env vars to flip the API to Cloud Tasks mode
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')
echo "5) Update $SERVICE_NAME env vars (RUNS_QUEUE / RUNS_WORKER_URL / RUNS_WORKER_SA)…"
gcloud run services update "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --update-env-vars="RUNS_QUEUE=${QUEUE_NAME},RUNS_WORKER_URL=${SERVICE_URL},RUNS_WORKER_SA=${WORKER_SA_EMAIL}" \
    >/dev/null
echo "   env vars updated; new revision rolling out"

# Also grant the API's runtime SA permission to enqueue tasks AND act as the
# worker SA (for OIDC token minting). The API runs as the default Compute SA
# unless overridden — find it.
RUNTIME_SA=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" --region="$REGION" \
    --format='value(spec.template.spec.serviceAccountName)')
if [[ -z "$RUNTIME_SA" ]]; then
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    echo "   (no SA override on $SERVICE_NAME — using default $RUNTIME_SA)"
fi

echo "6) Grant ${RUNTIME_SA} cloudtasks.enqueuer on the queue…"
gcloud tasks queues add-iam-policy-binding "$QUEUE_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/cloudtasks.enqueuer" >/dev/null

echo "7) Allow ${RUNTIME_SA} to mint OIDC tokens as ${WORKER_SA_EMAIL}…"
gcloud iam service-accounts add-iam-policy-binding "$WORKER_SA_EMAIL" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/iam.serviceAccountTokenCreator" >/dev/null

echo
echo "✅ Sprint C runs-queue ready for env=${ENV}."
echo "   POST /api/runs on $SERVICE_NAME will now enqueue Cloud Tasks tasks"
echo "   that POST /internal/tasks/run/{id} with an OIDC token from"
echo "   ${WORKER_SA_EMAIL}."
echo
echo "Verify with:"
echo "   curl -sI ${SERVICE_URL}/health"
echo "   gcloud tasks queues describe ${QUEUE_NAME} --location=${REGION} --project=${PROJECT_ID}"

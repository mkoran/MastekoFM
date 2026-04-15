#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT_ID="masteko-fm"
REGION="northamerica-northeast1"
SERVICE_NAME="masteko-fm-api-prod"

VERSION_FILE="VERSION"
VERSION=$(cat "$VERSION_FILE")
echo "Deploying PROD version: $VERSION"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]{3}$ ]]; then
    echo "ERROR: VERSION '$VERSION' does not match MAJOR.NNN format"
    exit 1
fi

echo ""
echo "You are about to deploy to PRODUCTION."
echo "Version: $VERSION"
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Building frontend..."
cd frontend
npm ci --silent 2>/dev/null || npm install --silent
npm run build
cd "$SCRIPT_DIR"

echo ""
echo "Submitting Cloud Build (PROD, auto-rollback enabled)..."
BUILD_OUTPUT=$(gcloud builds submit \
    --project="$PROJECT_ID" \
    --config=cloudbuild.yaml \
    --substitutions="_SERVICE_NAME=$SERVICE_NAME,_ENVIRONMENT=prod,_VERSION=$VERSION,_AUTO_ROLLBACK=true" \
    --async \
    --format="value(id)" \
    2>&1)

BUILD_ID=$(echo "$BUILD_OUTPUT" | tail -1)
echo "Build ID: $BUILD_ID"
echo "Polling for completion..."

MAX_WAIT=900
ELAPSED=0
INTERVAL=10

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    STATUS=$(gcloud builds describe "$BUILD_ID" \
        --project="$PROJECT_ID" \
        --format="value(status)" 2>/dev/null)

    case "$STATUS" in
        SUCCESS)
            echo "Cloud Build succeeded"
            break
            ;;
        FAILURE|INTERNAL_ERROR|TIMEOUT|CANCELLED|EXPIRED)
            echo "Cloud Build failed: $STATUS"
            exit 1
            ;;
        *)
            sleep $INTERVAL
            ELAPSED=$((ELAPSED + INTERVAL))
            ;;
    esac
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo "Cloud Build timed out after ${MAX_WAIT}s"
    exit 1
fi

echo ""
echo "Updating PROD resource settings..."
gcloud run services update "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --min-instances=1 \
    --cpu=2 \
    --memory=2Gi \
    --no-cpu-throttling \
    2>/dev/null

echo ""
echo "Deploying frontend to Firebase Hosting (prod)..."
firebase deploy --only hosting:prod --project "$PROJECT_ID"

echo ""
echo "Running health checks..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.url)" 2>/dev/null)

HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health")
FULL_HEALTH=$(curl -s "$SERVICE_URL/api/health/full")

echo "/health: $HEALTH_STATUS"
echo "/api/health/full: $FULL_HEALTH"

if [[ "$HEALTH_STATUS" != "200" ]]; then
    echo "Health check failed! Initiate rollback."
    exit 1
fi

echo ""
echo "========================================="
echo "  PROD deploy complete"
echo "  Version: $VERSION"
echo "  API: $SERVICE_URL"
echo "  Frontend: https://masteko-fm.web.app"
echo "========================================="
echo ""
echo "Tag this release (do NOT use -f):"
echo "  git tag prod-v$VERSION"
echo "  git push origin prod-v$VERSION"

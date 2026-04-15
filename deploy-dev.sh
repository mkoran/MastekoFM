#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT_ID="masteko-fm"
REGION="northamerica-northeast1"
SERVICE_NAME="masteko-fm-api-dev"

VERSION_FILE="VERSION"
if [[ ! -f "$VERSION_FILE" ]]; then
    echo "ERROR: VERSION file not found"
    exit 1
fi

CURRENT_VERSION=$(cat "$VERSION_FILE")
if [[ ! "$CURRENT_VERSION" =~ ^[0-9]+\.[0-9]{3}$ ]]; then
    echo "ERROR: VERSION '$CURRENT_VERSION' does not match MAJOR.NNN format"
    exit 1
fi

MAJOR="${CURRENT_VERSION%%.*}"
COUNTER="${CURRENT_VERSION##*.}"
COUNTER=$((10#$COUNTER + 1))
NEW_VERSION="${MAJOR}.$(printf '%03d' $COUNTER)"

echo "$NEW_VERSION" > "$VERSION_FILE"
echo "Version: $CURRENT_VERSION -> $NEW_VERSION"

echo ""
echo "Building frontend..."
cd frontend
npm ci --silent 2>/dev/null || npm install --silent
npm run build
cd "$SCRIPT_DIR"

echo ""
echo "Submitting Cloud Build..."
BUILD_OUTPUT=$(gcloud builds submit \
    --project="$PROJECT_ID" \
    --config=cloudbuild.yaml \
    --substitutions="_SERVICE_NAME=$SERVICE_NAME,_ENVIRONMENT=dev,_VERSION=$NEW_VERSION" \
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
            echo "View logs: https://console.cloud.google.com/cloud-build/builds/$BUILD_ID?project=$PROJECT_ID"
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
echo "Deploying frontend to Firebase Hosting (dev)..."
firebase deploy --only hosting:dev --project "$PROJECT_ID"

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
    echo "Health check failed!"
    exit 1
fi

echo ""
echo "========================================="
echo "  DEV deploy complete"
echo "  Version: $NEW_VERSION"
echo "  API: $SERVICE_URL"
echo "  Frontend: https://dev-masteko-fm.web.app"
echo "========================================="
echo ""
echo "VERSION was bumped to $NEW_VERSION."
echo "Review and commit when ready:"
echo "  git add VERSION && git commit -m 'chore: bump version to $NEW_VERSION'"

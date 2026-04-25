#!/usr/bin/env bash
# Sprint UX-01 post-deploy smoke tests.
#
# Run after a Cloud Run + Firebase Hosting deploy. Exits non-zero if any check
# fails — deploy-dev.yml / deploy-prod.yml use the exit code to gate traffic
# (PROD also auto-rolls back via _AUTO_ROLLBACK=true in cloudbuild.yaml).
#
# Required env vars:
#   API_BASE_URL    Cloud Run URL (e.g., https://masteko-fm-api-dev-...run.app)
#   HOSTING_URL    Firebase Hosting URL (e.g., https://dev-masteko-fm.web.app)
#
# Optional env var:
#   AUTH_TOKEN     Bearer token for authenticated checks. If empty, only
#                  unauthenticated endpoints are smoke-tested. CI sets this
#                  via DEV auth bypass (token "dev-ci-smoke@example.com")
#                  when DEV_AUTH_BYPASS=true on the service.
set -euo pipefail

API_BASE_URL="${API_BASE_URL:?API_BASE_URL is required}"
HOSTING_URL="${HOSTING_URL:?HOSTING_URL is required}"
AUTH_TOKEN="${AUTH_TOKEN:-}"

PASS=0
FAIL=0

check() {
    local name="$1"; shift
    local expected="$1"; shift
    local actual
    actual=$("$@" 2>&1) || true
    if [[ "$actual" == *"$expected"* || "$actual" == "$expected" ]]; then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name (expected '$expected', got '$actual')"
        FAIL=$((FAIL + 1))
    fi
}

http_status() {
    local url="$1"; shift
    local extra=("$@")
    curl -s -o /dev/null -w "%{http_code}" "${extra[@]}" "$url"
}

http_body_contains() {
    local url="$1"; shift
    local needle="$1"; shift
    local extra=("$@")
    local body
    body=$(curl -s "${extra[@]}" "$url")
    [[ "$body" == *"$needle"* ]] && echo "$needle" || echo "MISS"
}

echo "── Backend health ─────────────────────────────────────────────"
check "/health returns 200" "200" http_status "$API_BASE_URL/health"
check "/api/health/full returns 200" "200" http_status "$API_BASE_URL/api/health/full"
check "/api/health/full reports api ok" "ok" http_body_contains "$API_BASE_URL/api/health/full" '"api":"ok"'

echo
echo "── Auth surface ───────────────────────────────────────────────"
check "/api/projects returns 401 unauthenticated" "401" http_status "$API_BASE_URL/api/projects"

if [[ -n "$AUTH_TOKEN" ]]; then
    AUTH=( -H "Authorization: Bearer $AUTH_TOKEN" )
    echo
    echo "── Authenticated endpoints (UX-01 smoke) ──────────────────────"
    check "/api/projects 200 with auth"               "200" http_status "$API_BASE_URL/api/projects" "${AUTH[@]}"
    check "/api/models 200 with auth"                 "200" http_status "$API_BASE_URL/api/models" "${AUTH[@]}"
    check "/api/output-templates 200 with auth"       "200" http_status "$API_BASE_URL/api/output-templates" "${AUTH[@]}"
    check "/api/runs 200 with auth"                   "200" http_status "$API_BASE_URL/api/runs" "${AUTH[@]}"
    check "/api/projects?include_archived=true 200"   "200" http_status "$API_BASE_URL/api/projects?include_archived=true" "${AUTH[@]}"
    check "/api/seed/helloworld 400 without drive token" "400" http_status -X POST "$API_BASE_URL/api/seed/helloworld" "${AUTH[@]}"
fi

echo
echo "── Frontend (UX-01-05) ────────────────────────────────────────"
check "Hosting root returns 200" "200" http_status "$HOSTING_URL/"
check "Hosting serves MastekoFM bundle" "MastekoFM" http_body_contains "$HOSTING_URL/" "MastekoFM"
# index.html is set to no-cache in firebase.json — verify the header survived
check "index.html sends no-cache" "no-cache" bash -c "curl -sI '$HOSTING_URL/' | tr -d '\r'"

echo
echo "──────────────────────────────────────────────────────────────"
echo "Smoke result: $PASS passed, $FAIL failed"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi

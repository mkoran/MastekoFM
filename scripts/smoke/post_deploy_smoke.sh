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
#
# Note: avoids set -u because macOS bash 3.2 mishandles empty arrays under it.
set -eo pipefail

API_BASE_URL="${API_BASE_URL:?API_BASE_URL is required}"
HOSTING_URL="${HOSTING_URL:?HOSTING_URL is required}"
AUTH_TOKEN="${AUTH_TOKEN:-}"
AUTH_HEADER=""
if [[ -n "$AUTH_TOKEN" ]]; then
    AUTH_HEADER="Authorization: Bearer $AUTH_TOKEN"
fi

PASS=0
FAIL=0

# Fetch the HTTP status code for a GET (or POST with $1 == "POST").
status_get() {
    local url="$1"
    if [[ -n "$AUTH_HEADER" ]]; then
        curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$url"
    else
        curl -s -o /dev/null -w "%{http_code}" "$url"
    fi
}

status_get_noauth() {
    local url="$1"
    curl -s -o /dev/null -w "%{http_code}" "$url"
}

status_post() {
    local url="$1"
    if [[ -n "$AUTH_HEADER" ]]; then
        curl -s -o /dev/null -w "%{http_code}" -X POST -H "$AUTH_HEADER" "$url"
    else
        curl -s -o /dev/null -w "%{http_code}" -X POST "$url"
    fi
}

body_get() {
    local url="$1"
    if [[ -n "$AUTH_HEADER" ]]; then
        curl -s -H "$AUTH_HEADER" "$url"
    else
        curl -s "$url"
    fi
}

headers_get() {
    local url="$1"
    curl -sI "$url" | tr -d '\r'
}

# assert_eq <name> <expected> <actual>
assert_eq() {
    local name="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name (expected '$expected', got '$actual')"
        FAIL=$((FAIL + 1))
    fi
}

# assert_contains <name> <needle> <haystack>
assert_contains() {
    local name="$1" needle="$2" haystack="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name (missing '$needle')"
        FAIL=$((FAIL + 1))
    fi
}

echo "── Backend health ─────────────────────────────────────────────"
assert_eq       "/health returns 200"            "200" "$(status_get_noauth "$API_BASE_URL/health")"
assert_eq       "/api/health/full returns 200"   "200" "$(status_get_noauth "$API_BASE_URL/api/health/full")"
assert_contains "/api/health/full reports api ok" '"api":"ok"' "$(curl -s "$API_BASE_URL/api/health/full")"

echo
echo "── Auth surface ───────────────────────────────────────────────"
assert_eq "/api/projects returns 401 unauthenticated" "401" "$(status_get_noauth "$API_BASE_URL/api/projects")"

if [[ -n "$AUTH_TOKEN" ]]; then
    echo
    echo "── Authenticated endpoints (UX-01 smoke) ──────────────────────"
    assert_eq "/api/projects 200 with auth"             "200" "$(status_get "$API_BASE_URL/api/projects")"
    assert_eq "/api/models 200 with auth"               "200" "$(status_get "$API_BASE_URL/api/models")"
    assert_eq "/api/output-templates 200 with auth"     "200" "$(status_get "$API_BASE_URL/api/output-templates")"
    assert_eq "/api/runs 200 with auth"                 "200" "$(status_get "$API_BASE_URL/api/runs")"
    assert_eq "/api/projects?include_archived=true 200" "200" "$(status_get "$API_BASE_URL/api/projects?include_archived=true")"
    assert_eq "/api/seed/helloworld 400 without drive token" "400" "$(status_post "$API_BASE_URL/api/seed/helloworld")"
fi

echo
echo "── Frontend (UX-01-05) ────────────────────────────────────────"
assert_eq       "Hosting root returns 200"      "200"        "$(status_get_noauth "$HOSTING_URL/")"
assert_contains "Hosting serves MastekoFM bundle" "MastekoFM"  "$(curl -s "$HOSTING_URL/")"
# index.html is set to no-cache in firebase.json — verify the header survived
assert_contains "index.html sends no-cache"     "no-cache"   "$(headers_get "$HOSTING_URL/")"

echo
echo "──────────────────────────────────────────────────────────────"
echo "Smoke result: $PASS passed, $FAIL failed"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi

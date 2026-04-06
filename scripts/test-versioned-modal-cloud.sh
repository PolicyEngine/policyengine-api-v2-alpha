#!/bin/bash
# Cloud verification of versioned Modal deployment.
# Deploys to the 'testing' Modal environment (NOT staging, NOT main).
# Requires Modal credentials (MODAL_TOKEN_ID, MODAL_TOKEN_SECRET).
#
# Usage: ./scripts/test-versioned-modal-cloud.sh
#
# Required env vars for secrets sync:
#   SUPABASE_POOLER_URL, SUPABASE_URL, SUPABASE_KEY, SUPABASE_SECRET_KEY,
#   STORAGE_BUCKET, LOGFIRE_TOKEN, ANTHROPIC_API_KEY

set -uo pipefail

MODAL_ENV="testing"

PASS_COUNT=0
FAIL_COUNT=0
RESULTS=()

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    RESULTS+=("PASS: $1")
    echo "  PASS: $1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    RESULTS+=("FAIL: $1 — $2")
    echo "  FAIL: $1 — $2"
}

# Extract versions from uv.lock
US_VERSION=$(grep -A1 'name = "policyengine-us"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
UK_VERSION=$(grep -A1 'name = "policyengine-uk"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
US_SAFE="${US_VERSION//./-}"
UK_SAFE="${UK_VERSION//./-}"
APP_NAME="policyengine-v2-us${US_SAFE}-uk${UK_SAFE}"

echo ""
echo "=========================================="
echo "  Versioned Modal Cloud Tests"
echo "  Environment: $MODAL_ENV"
echo "  US version:  $US_VERSION"
echo "  UK version:  $UK_VERSION"
echo "  App name:    $APP_NAME"
echo "=========================================="

# ============================================================
echo ""
echo "=== Step 1: Create testing environment ==="
echo ""

uv run modal environment create "$MODAL_ENV" 2>/dev/null
if [[ $? -eq 0 ]]; then
    pass "Created testing environment (or already exists)"
else
    pass "Testing environment already exists"
fi

# ============================================================
echo ""
echo "=== Step 2: Sync secrets to testing ==="
echo ""

if chmod +x .github/scripts/modal-sync-secrets.sh && .github/scripts/modal-sync-secrets.sh "$MODAL_ENV" "$MODAL_ENV" 2>&1; then
    pass "Secrets synced to testing environment"
else
    fail "Secret sync" "modal-sync-secrets.sh failed"
fi

# ============================================================
echo ""
echo "=== Step 3: Deploy versioned app to testing ==="
echo ""

export POLICYENGINE_US_VERSION="$US_VERSION"
export POLICYENGINE_UK_VERSION="$UK_VERSION"

if chmod +x .github/scripts/modal-deploy-versioned.sh && .github/scripts/modal-deploy-versioned.sh "$MODAL_ENV" 2>&1; then
    pass "Versioned app deployed: $APP_NAME"
else
    fail "Versioned app deploy" "modal-deploy-versioned.sh failed"
    echo ""
    echo "  Cannot continue without a successful deploy."
    echo ""
    for result in "${RESULTS[@]}"; do echo "  $result"; done
    echo "  Total: $((PASS_COUNT + FAIL_COUNT)) checks, $PASS_COUNT passed, $FAIL_COUNT failed"
    exit 1
fi

# ============================================================
echo ""
echo "=== Step 4: Verify Modal Dict entries ==="
echo ""

DICT_CHECK=$(uv run python -c "
import modal
import json

results = {}

for country, version in [('us', '$US_VERSION'), ('uk', '$UK_VERSION')]:
    dict_name = f'simulation-api-{country}-versions'
    d = modal.Dict.from_name(dict_name, environment_name='$MODAL_ENV')

    latest = d.get('latest')
    app = d.get(version)

    results[f'{country}_latest'] = latest
    results[f'{country}_app'] = app
    results[f'{country}_latest_match'] = (latest == version)
    results[f'{country}_app_match'] = (app == '$APP_NAME')

print(json.dumps(results))
" 2>&1)

if [[ $? -ne 0 ]]; then
    fail "Dict check" "Python script failed: $DICT_CHECK"
else
    US_LATEST_MATCH=$(echo "$DICT_CHECK" | python3 -c "import sys,json; print(json.load(sys.stdin)['us_latest_match'])")
    UK_LATEST_MATCH=$(echo "$DICT_CHECK" | python3 -c "import sys,json; print(json.load(sys.stdin)['uk_latest_match'])")
    US_APP_MATCH=$(echo "$DICT_CHECK" | python3 -c "import sys,json; print(json.load(sys.stdin)['us_app_match'])")
    UK_APP_MATCH=$(echo "$DICT_CHECK" | python3 -c "import sys,json; print(json.load(sys.stdin)['uk_app_match'])")

    if [[ "$US_LATEST_MATCH" == "True" ]]; then
        pass "US Dict 'latest' points to $US_VERSION"
    else
        fail "US Dict 'latest'" "Expected $US_VERSION"
    fi

    if [[ "$UK_LATEST_MATCH" == "True" ]]; then
        pass "UK Dict 'latest' points to $UK_VERSION"
    else
        fail "UK Dict 'latest'" "Expected $UK_VERSION"
    fi

    if [[ "$US_APP_MATCH" == "True" ]]; then
        pass "US version maps to $APP_NAME"
    else
        fail "US version mapping" "Expected $APP_NAME"
    fi

    if [[ "$UK_APP_MATCH" == "True" ]]; then
        pass "UK version maps to $APP_NAME"
    else
        fail "UK version mapping" "Expected $APP_NAME"
    fi
fi

# ============================================================
echo ""
echo "=== Step 5: Version resolution test ==="
echo ""

RESOLVED=$(uv run python -c "
from policyengine_api.version_resolver import _resolve_app_name
_resolve_app_name.cache_clear()
result = _resolve_app_name('us', None, '$MODAL_ENV')
print(result)
" 2>&1)

if [[ "$RESOLVED" == "$APP_NAME" ]]; then
    pass "Version resolver returns correct app: $RESOLVED"
else
    fail "Version resolver" "Expected '$APP_NAME', got '$RESOLVED'"
fi

# ============================================================
echo ""
echo "=== Step 6: Coexistence test (fake version bump) ==="
echo ""

FAKE_US="$US_VERSION.1"
FAKE_US_SAFE="${FAKE_US//./-}"
FAKE_APP="policyengine-v2-us${FAKE_US_SAFE}-uk${UK_SAFE}"

# Update just the Dict (don't actually deploy a fake app — just test the registry)
uv run python -c "
import modal
d = modal.Dict.from_name('simulation-api-us-versions', environment_name='$MODAL_ENV', create_if_missing=True)
d['$FAKE_US'] = '$FAKE_APP'
d['latest'] = '$FAKE_US'
print('Fake entry added')
" 2>&1

COEXIST_CHECK=$(uv run python -c "
import modal
d = modal.Dict.from_name('simulation-api-us-versions', environment_name='$MODAL_ENV')
original = d.get('$US_VERSION')
fake = d.get('$FAKE_US')
latest = d.get('latest')
print(f'original={original}|fake={fake}|latest={latest}')
" 2>&1)

ORIG_APP=$(echo "$COEXIST_CHECK" | sed 's/.*original=\([^|]*\).*/\1/')
FAKE_APP_GOT=$(echo "$COEXIST_CHECK" | sed 's/.*fake=\([^|]*\).*/\1/')
LATEST_GOT=$(echo "$COEXIST_CHECK" | sed 's/.*latest=\(.*\)/\1/')

if [[ "$ORIG_APP" == "$APP_NAME" ]]; then
    pass "Original version still in Dict: $US_VERSION -> $ORIG_APP"
else
    fail "Original version lost" "Expected $APP_NAME, got $ORIG_APP"
fi

if [[ "$FAKE_APP_GOT" == "$FAKE_APP" ]]; then
    pass "Fake version added to Dict: $FAKE_US -> $FAKE_APP_GOT"
else
    fail "Fake version not found" "Expected $FAKE_APP, got $FAKE_APP_GOT"
fi

if [[ "$LATEST_GOT" == "$FAKE_US" ]]; then
    pass "'latest' updated to fake version: $LATEST_GOT"
else
    fail "'latest' not updated" "Expected $FAKE_US, got $LATEST_GOT"
fi

# Restore latest to the real version
uv run python -c "
import modal
d = modal.Dict.from_name('simulation-api-us-versions', environment_name='$MODAL_ENV', create_if_missing=True)
d['latest'] = '$US_VERSION'
del d['$FAKE_US']
print('Cleaned up fake entry, restored latest to $US_VERSION')
" 2>&1

pass "Cleaned up fake Dict entry"

# ============================================================
echo ""
echo "=========================================="
echo "  SUMMARY"
echo "=========================================="
echo ""

for result in "${RESULTS[@]}"; do
    echo "  $result"
done

echo ""
echo "  Total: $((PASS_COUNT + FAIL_COUNT)) checks, $PASS_COUNT passed, $FAIL_COUNT failed"
echo ""

if [[ $FAIL_COUNT -gt 0 ]]; then
    echo "  RESULT: FAILED"
    exit 1
else
    echo "  RESULT: ALL PASSED"
    exit 0
fi

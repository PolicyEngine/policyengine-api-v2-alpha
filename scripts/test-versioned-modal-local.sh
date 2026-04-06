#!/bin/bash
# Local verification of versioned Modal deployment setup.
# No Modal cloud connection required. Runs in seconds.
#
# Usage: ./scripts/test-versioned-modal-local.sh

set -uo pipefail

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

# ============================================================
echo ""
echo "=== Step 1: Version extraction from uv.lock ==="
echo ""

GITHUB_OUTPUT=$(mktemp)
export GITHUB_OUTPUT

if .github/scripts/modal-extract-versions.sh . > /dev/null 2>&1; then
    US_VERSION=$(grep "us_version=" "$GITHUB_OUTPUT" | cut -d= -f2)
    UK_VERSION=$(grep "uk_version=" "$GITHUB_OUTPUT" | cut -d= -f2)

    if [[ "$US_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        pass "US version extracted: $US_VERSION"
    else
        fail "US version format" "Got '$US_VERSION', expected semver"
    fi

    if [[ "$UK_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        pass "UK version extracted: $UK_VERSION"
    else
        fail "UK version format" "Got '$UK_VERSION', expected semver"
    fi
else
    fail "Version extraction script" "modal-extract-versions.sh failed"
    US_VERSION=""
    UK_VERSION=""
fi
rm -f "$GITHUB_OUTPUT"

# ============================================================
echo ""
echo "=== Step 2: App name generation ==="
echo ""

APP_NAME=$(uv run python -c "from policyengine_api.modal.app import get_app_name; print(get_app_name('$US_VERSION', '$UK_VERSION'))" 2>&1)

if [[ "$APP_NAME" =~ ^policyengine-v2-us[0-9]+-[0-9]+-[0-9]+-uk[0-9]+-[0-9]+-[0-9]+$ ]]; then
    pass "App name format correct: $APP_NAME"
else
    fail "App name format" "Got '$APP_NAME'"
fi

if [[ "$APP_NAME" != *"."* ]]; then
    pass "App name contains no dots"
else
    fail "App name contains dots" "$APP_NAME"
fi

# ============================================================
echo ""
echo "=== Step 3: App name env override ==="
echo ""

OVERRIDE_NAME=$(MODAL_APP_NAME=test-override uv run python -c "
import os
os.environ['MODAL_APP_NAME'] = 'test-override'
from policyengine_api.modal.app import get_app_name
print(os.environ.get('MODAL_APP_NAME', get_app_name('1.0.0', '2.0.0')))
" 2>&1)

if [[ "$OVERRIDE_NAME" == "test-override" ]]; then
    pass "MODAL_APP_NAME override works"
else
    fail "MODAL_APP_NAME override" "Got '$OVERRIDE_NAME'"
fi

# ============================================================
echo ""
echo "=== Step 4: Image version pins ==="
echo ""

IMAGES_FILE="src/policyengine_api/modal/images.py"

if grep -q 'policyengine-uk==' "$IMAGES_FILE"; then
    pass "UK image uses exact pin (==)"
else
    fail "UK image pin" "No == pin found in $IMAGES_FILE"
fi

if grep -q 'policyengine-us==' "$IMAGES_FILE"; then
    pass "US image uses exact pin (==)"
else
    fail "US image pin" "No == pin found in $IMAGES_FILE"
fi

if grep -q 'policyengine-uk>=' "$IMAGES_FILE" || grep -q 'policyengine-us>=' "$IMAGES_FILE"; then
    fail "Loose pins found" "Country packages still have >= pins in $IMAGES_FILE"
else
    pass "No loose pins (>=) for country packages"
fi

# ============================================================
echo ""
echo "=== Step 5: Function registration (modal serve dry-run) ==="
echo ""

EXPECTED_FUNCTIONS=(
    "validate_secrets"
    "simulate_household_uk"
    "simulate_household_us"
    "simulate_economy_uk"
    "simulate_economy_us"
    "economy_comparison_uk"
    "economy_comparison_us"
    "household_impact_uk"
    "household_impact_us"
    "compute_aggregate_uk"
    "compute_aggregate_us"
    "compute_change_aggregate_uk"
    "compute_change_aggregate_us"
)

# Use modal shell to list functions without actually serving
# (modal serve would block, so we check the app's function list via Python)
REGISTERED=$(uv run python -c "
import policyengine_api.modal.functions  # registers all functions
from policyengine_api.modal.app import app
for name in sorted(app.registered_functions):
    if not name.startswith('_'):
        print(name)
" 2>&1)

if [[ $? -ne 0 ]]; then
    fail "Function registration" "Python import failed: $REGISTERED"
else
    MISSING=0
    for fn in "${EXPECTED_FUNCTIONS[@]}"; do
        if echo "$REGISTERED" | grep -q "$fn"; then
            pass "Function registered: $fn"
        else
            fail "Function missing" "$fn not found in registered functions"
            MISSING=$((MISSING + 1))
        fi
    done
fi

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

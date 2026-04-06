#!/bin/bash
# Deploy versioned simulation app to Modal
# Usage: ./modal-deploy-versioned.sh <modal-environment>
# Required env vars: POLICYENGINE_US_VERSION, POLICYENGINE_UK_VERSION
#
# Deploys a versioned app named policyengine-us{X}-uk{Y} and updates
# the Modal Dict version registries so Cloud Run can route to it.
# No separate gateway app — Cloud Run handles routing directly.

set -euo pipefail

MODAL_ENV="${1:?Modal environment required (staging or main)}"

# Validate required env vars
: "${POLICYENGINE_US_VERSION:?POLICYENGINE_US_VERSION must be set}"
: "${POLICYENGINE_UK_VERSION:?POLICYENGINE_UK_VERSION must be set}"

# Generate versioned app name (dots replaced with dashes)
US_VERSION_SAFE="${POLICYENGINE_US_VERSION//./-}"
UK_VERSION_SAFE="${POLICYENGINE_UK_VERSION//./-}"
APP_NAME="policyengine-us${US_VERSION_SAFE}-uk${UK_VERSION_SAFE}"

echo "========================================"
echo "Deploying versioned Modal simulation app"
echo "  Environment: $MODAL_ENV"
echo "  App name:    $APP_NAME"
echo "  US version:  ${POLICYENGINE_US_VERSION}"
echo "  UK version:  ${POLICYENGINE_UK_VERSION}"
echo "========================================"

# 1. Deploy the versioned app
echo ""
echo "Step 1: Deploying versioned app..."
export MODAL_APP_NAME="$APP_NAME"
uv run modal deploy --env="$MODAL_ENV" src/policyengine_api/modal/deploy.py

# 2. Update version registries
echo ""
echo "Step 2: Updating version registries..."
uv run python scripts/update_version_registry.py \
    --app-name "$APP_NAME" \
    --us-version "${POLICYENGINE_US_VERSION}" \
    --uk-version "${POLICYENGINE_UK_VERSION}" \
    --environment "$MODAL_ENV"

echo ""
echo "========================================"
echo "Deployment complete: $APP_NAME"
echo "========================================"

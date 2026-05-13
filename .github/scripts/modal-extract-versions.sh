#!/bin/bash
# Extract policyengine, policyengine-us, and policyengine-uk versions from uv.lock
# Usage: ./modal-extract-versions.sh [project-dir]
# Outputs: Sets policyengine_version, us_version, and uk_version in GITHUB_OUTPUT

set -euo pipefail

PROJECT_DIR="${1:-.}"

cd "$PROJECT_DIR"

POLICYENGINE_VERSION=$(grep -A1 'name = "policyengine"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
US_VERSION=$(grep -A1 'name = "policyengine-us"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')
UK_VERSION=$(grep -A1 'name = "policyengine-uk"' uv.lock | grep version | head -1 | sed 's/.*"\(.*\)".*/\1/')

if [ -z "$POLICYENGINE_VERSION" ] || [ -z "$US_VERSION" ] || [ -z "$UK_VERSION" ]; then
    echo "ERROR: Could not extract versions from uv.lock"
    echo "  POLICYENGINE_VERSION=$POLICYENGINE_VERSION"
    echo "  US_VERSION=$US_VERSION"
    echo "  UK_VERSION=$UK_VERSION"
    exit 1
fi

echo "policyengine_version=$POLICYENGINE_VERSION" >> "$GITHUB_OUTPUT"
echo "us_version=$US_VERSION" >> "$GITHUB_OUTPUT"
echo "uk_version=$UK_VERSION" >> "$GITHUB_OUTPUT"
echo "Extracted versions: policyengine=$POLICYENGINE_VERSION, policyengine-us=$US_VERSION, policyengine-uk=$UK_VERSION"

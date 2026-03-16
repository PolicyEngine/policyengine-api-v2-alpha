#!/usr/bin/env bash
#
# Check if a Python package has a newer version on PyPI than what's
# locked in uv.lock. If so, upgrade the lockfile and open a PR.
#
# Usage: ./update-package.sh <package-name>
#
# Requires: uv, gh (GitHub CLI), curl, jq, git
# Environment: GH_TOKEN must be set for gh CLI

set -euo pipefail

PACKAGE="${1:?Usage: update-package.sh <package-name>}"

# 1. Get current locked version from uv.lock
CURRENT=$(grep -A1 "^name = \"${PACKAGE}\"$" uv.lock | grep 'version' | head -1 | sed 's/.*"\(.*\)"/\1/')
if [[ -z "$CURRENT" ]]; then
  echo "ERROR: Package '${PACKAGE}' not found in uv.lock"
  exit 1
fi
echo "Current locked version: ${PACKAGE}==${CURRENT}"

# 2. Get latest version from PyPI
LATEST=$(curl -sf "https://pypi.org/pypi/${PACKAGE}/json" | jq -r .info.version)
if [[ -z "$LATEST" ]]; then
  echo "ERROR: Could not fetch latest version for '${PACKAGE}' from PyPI"
  exit 1
fi
echo "Latest PyPI version:   ${PACKAGE}==${LATEST}"

# 3. Compare
if [[ "$CURRENT" == "$LATEST" ]]; then
  echo "Already up to date. Nothing to do."
  exit 0
fi
echo "Update available: ${CURRENT} -> ${LATEST}"

# 4. Check if a PR already exists for this package+version
EXISTING_PR=$(gh pr list --search "in:title update ${PACKAGE} to ${LATEST}" --state open --json number --jq '.[0].number' 2>/dev/null || true)
if [[ -n "$EXISTING_PR" ]]; then
  echo "PR #${EXISTING_PR} already exists for this update. Skipping."
  exit 0
fi

# 5. Configure git author
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# 6. Update pinned version in pyproject.toml and upgrade lockfile
echo "Updating ${PACKAGE} pin in pyproject.toml: ==${CURRENT} -> ==${LATEST}"
sed -i "s/\"${PACKAGE}==${CURRENT}\"/\"${PACKAGE}==${LATEST}\"/" pyproject.toml

echo "Running: uv lock --upgrade-package ${PACKAGE}"
uv lock --upgrade-package "${PACKAGE}"

if git diff --quiet uv.lock pyproject.toml; then
  echo "No changes after upgrade. Nothing to do."
  exit 0
fi

# 7. Create branch, commit, push, open PR
BRANCH="auto/update-${PACKAGE}-${LATEST}"
git checkout -b "$BRANCH"
git add uv.lock pyproject.toml
git commit -m "chore(deps): update ${PACKAGE} to ${LATEST}"
git push -u origin "$BRANCH"

gh pr create \
  --title "chore(deps): update ${PACKAGE} to ${LATEST}" \
  --body "Update ${PACKAGE} to ${LATEST}"

echo "PR created for ${PACKAGE} ${CURRENT} -> ${LATEST}"

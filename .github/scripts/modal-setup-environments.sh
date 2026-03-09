#!/bin/bash
# Ensure Modal environments exist (idempotent)
set -euo pipefail

echo "Setting up Modal environments..."
uv run modal environment create staging 2>/dev/null || echo "staging environment already exists"
echo "Modal environments ready"

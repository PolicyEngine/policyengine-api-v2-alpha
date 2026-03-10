#!/bin/bash
# Sync secrets from GitHub Actions to a Modal environment
# Usage: ./modal-sync-secrets.sh <modal-environment> <logfire-environment>
# Required env vars: SUPABASE_DB_URL, SUPABASE_URL, SUPABASE_KEY, SUPABASE_SECRET_KEY, LOGFIRE_TOKEN
set -euo pipefail

MODAL_ENV="${1:?Modal environment required (staging or main)}"
LOGFIRE_ENV="${2:?Logfire environment required (staging or prod)}"

echo "Syncing secrets to Modal environment: $MODAL_ENV"

uv run modal secret create policyengine-db \
  "DATABASE_URL=${SUPABASE_DB_URL}" \
  "SUPABASE_URL=${SUPABASE_URL}" \
  "SUPABASE_KEY=${SUPABASE_KEY}" \
  "SUPABASE_SECRET_KEY=${SUPABASE_SECRET_KEY}" \
  "STORAGE_BUCKET=${STORAGE_BUCKET:-datasets}" \
  --env="$MODAL_ENV" \
  --force

uv run modal secret create policyengine-logfire \
  "LOGFIRE_TOKEN=${LOGFIRE_TOKEN}" \
  "LOGFIRE_ENVIRONMENT=${LOGFIRE_ENV}" \
  --env="$MODAL_ENV" \
  --force

echo "Secrets synced to Modal environment: $MODAL_ENV"

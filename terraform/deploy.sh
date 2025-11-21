#!/bin/bash

# Load environment variables from .env file
set -a
source ../.env
set +a

# Export as Terraform variables
export TF_VAR_supabase_url="$SUPABASE_URL"
export TF_VAR_supabase_key="$SUPABASE_KEY"
export TF_VAR_supabase_db_url="$SUPABASE_DB_URL"
export TF_VAR_logfire_token="$LOGFIRE_TOKEN"
export TF_VAR_storage_bucket="${STORAGE_BUCKET:-datasets}"

# Run terraform with the provided command
terraform "$@"

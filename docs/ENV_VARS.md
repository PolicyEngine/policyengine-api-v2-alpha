# Environment variables

This document tracks all environment variables across services to avoid configuration drift.

## Overview

| Service | Config location | Secrets storage |
|---------|----------------|-----------------|
| Local dev | `.env` file | Local file |
| Cloud Run (API) | Terraform | GitHub Secrets |
| Modal.com | Modal secrets | Modal dashboard |
| GitHub Actions | Workflow files | GitHub Secrets |

## Variables by service

### Local development (`.env`)

Copy `.env.example` to `.env` and configure:

```bash
# Supabase (from `supabase start` output)
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_KEY=eyJ...                    # anon key
SUPABASE_SERVICE_KEY=eyJ...            # service key (for admin ops)
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# Storage
STORAGE_BUCKET=datasets

# API
API_TITLE=PolicyEngine API
API_VERSION=0.1.0
API_PORT=8000
DEBUG=true

# Observability
LOGFIRE_TOKEN=...                      # from logfire.pydantic.dev
LOGFIRE_ENVIRONMENT=local

# Modal (for local testing of Modal functions)
MODAL_TOKEN_ID=ak-...
MODAL_TOKEN_SECRET=as-...
```

### Cloud Run API (Terraform)

Set via Terraform variables in `terraform/variables.tf`. Values come from GitHub Secrets during CI deploy.

| Variable | Terraform var | GitHub Secret |
|----------|--------------|---------------|
| `SUPABASE_URL` | `supabase_url` | `SUPABASE_URL` |
| `SUPABASE_KEY` | `supabase_key` | `SUPABASE_KEY` |
| `DATABASE_URL` | `supabase_db_url` | `SUPABASE_DB_URL` |
| `STORAGE_BUCKET` | `storage_bucket` | (default: `datasets`) |
| `LOGFIRE_TOKEN` | `logfire_token` | `LOGFIRE_TOKEN` |
| `LOGFIRE_ENVIRONMENT` | `logfire_environment` | (default: `prod`) |
| `MODAL_TOKEN_ID` | `modal_token_id` | `MODAL_TOKEN_ID` |
| `MODAL_TOKEN_SECRET` | `modal_token_secret` | `MODAL_TOKEN_SECRET` |

### Modal.com secrets

Modal functions read secrets from a Modal secret named `policyengine-db`. Configure via Modal dashboard or CLI:

```bash
modal secret create policyengine-db \
  DATABASE_URL="postgresql://..." \
  SUPABASE_URL="https://xxx.supabase.co" \
  SUPABASE_KEY="eyJ..." \
  STORAGE_BUCKET="datasets"
```

| Secret key | Description |
|------------|-------------|
| `DATABASE_URL` | Supabase Postgres connection string (use connection pooler for IPv4) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon or service key |
| `STORAGE_BUCKET` | Supabase storage bucket name |

### GitHub Actions secrets

Required secrets for CI/CD (set in repo Settings > Secrets):

| Secret | Used for |
|--------|----------|
| `SUPABASE_URL` | Terraform deploy |
| `SUPABASE_KEY` | Terraform deploy |
| `SUPABASE_DB_URL` | Terraform deploy |
| `LOGFIRE_TOKEN` | Terraform deploy |
| `MODAL_TOKEN_ID` | Terraform deploy + Modal deploy |
| `MODAL_TOKEN_SECRET` | Terraform deploy + Modal deploy |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | GCP auth |
| `GCP_SERVICE_ACCOUNT` | GCP auth |

GitHub Actions variables (Settings > Variables):

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | `policyengine-api-v2-alpha` |
| `GCP_REGION` | `us-central1` |
| `PROJECT_NAME` | `policyengine-api-v2-alpha` |
| `API_SERVICE_NAME` | Cloud Run service name |

## Database URLs

Supabase provides multiple connection options:

| Type | Use case | URL format |
|------|----------|-----------|
| Direct | Local dev | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| Pooler (transaction) | Cloud Run, Modal | `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres` |
| Pooler (session) | Long connections | Same as above but port `5432` |

Use the **transaction pooler** (port 6543) for serverless environments like Modal - it handles IPv4 and connection limits properly.

## Adding new environment variables

1. Add to `.env.example` with description
2. Add to `terraform/variables.tf` if needed for Cloud Run
3. Add to Modal secret if needed for compute functions
4. Add to GitHub Secrets if needed for CI/CD
5. Update this document

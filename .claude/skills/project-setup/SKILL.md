---
name: Project Setup
description: >
  This skill should be used when the user asks about "local development setup",
  "how to run locally", "set up the project", "install dependencies", "start the API",
  "configure environment", "deploy to production", "production setup", "GCP setup",
  "Terraform setup", "GitHub secrets", "GitHub environments", "Modal setup",
  "Supabase setup", "seed the database", "initialize database", "docker compose",
  "workload identity federation", "WIF setup", "service account setup",
  "deploy pipeline", "staging environment", "custom domain",
  "environment variables", ".env setup", "rollback a deploy", "run tests locally",
  or needs to understand how to get the project running from scratch.
  Also relevant when onboarding a new developer or setting up a new deployment.
version: 0.1.0
---

# Project Setup

To set up the PolicyEngine API v2 for local development or production deployment, follow the steps below. For the full step-by-step guide with exact commands, consult `references/runbook.md`.

## Architecture Overview

The API runs on three services:

| Service | Purpose | Local | Production |
|---------|---------|-------|------------|
| **FastAPI** | HTTP API | Docker Compose (port 8000) | GCP Cloud Run |
| **Supabase** | Database + storage | Supabase CLI (ports 54321/54322) | Managed Supabase |
| **Modal** | Serverless compute | `modal serve` | Modal.com (`main` env) |

## Local Development Quick Start

Prerequisites: `uv`, Supabase CLI, Docker.

```bash
make install                  # install Python deps
cp .env.example .env          # create env file
supabase start                # start local Postgres (copy keys to .env)
make init                     # Alembic migrations + storage bucket + RLS
make seed                     # seed UK/US models, datasets (~5 min)
make dev                      # start API at http://localhost:8000
```

Optional — to run simulations:

```bash
modal setup                   # authenticate with Modal (one-time)
make modal-deploy             # deploy serverless functions
```

### Environment Variables

The `.env.example` file documents all variables. For local dev, only three need manual entry:

| Variable | Source |
|----------|--------|
| `SUPABASE_KEY` | Output of `supabase start` (anon key) |
| `SUPABASE_SERVICE_KEY` | Output of `supabase start` (service_role key) |
| `HUGGING_FACE_TOKEN` | huggingface.co/settings/tokens (for seeding datasets) |

### Common Local Commands

```bash
make test              # unit tests
make integration-test  # full integration (starts Supabase, inits, seeds, tests)
make format            # ruff format
make lint              # ruff lint --fix
make db-reset-local    # drop everything, recreate, reseed
make logs              # docker compose logs -f
```

## Production Deployment

Production requires one-time infrastructure setup, after which deployment is fully automated via GitHub Actions on merge to main.

### One-Time Setup Sequence

1. **GCP project** — create project, enable APIs (`run`, `artifactregistry`, `iam`, `iamcredentials`)
2. **Terraform state bucket** — GCS bucket `policyengine-api-v2-alpha-terraform` with versioning
3. **Service account** — `github-deploy@PROJECT.iam.gserviceaccount.com` with roles: `run.admin`, `artifactregistry.admin`, `iam.serviceAccountUser`, `storage.admin`
4. **Workload Identity Federation** — OIDC pool + provider for GitHub Actions (no long-lived keys)
5. **Supabase project** — collect URL, anon key, direct connection string (port 5432)
6. **Modal.com** — create account, generate API token
7. **GitHub secrets** — 6 repo-level secrets + 2 environment-scoped secrets per environment
8. **GitHub environments** — `production` and `staging`

For exact commands and values, consult `references/runbook.md`.

### GitHub Secrets Layout

**Repo-level** (shared by all environments):

| Secret | Source |
|--------|--------|
| `SUPABASE_URL` | Supabase dashboard |
| `SUPABASE_KEY` | Supabase dashboard |
| `SUPABASE_DB_URL` | Supabase dashboard (direct connection, port 5432) |
| `LOGFIRE_TOKEN` | Logfire dashboard |
| `MODAL_TOKEN_ID` | Modal.com settings |
| `MODAL_TOKEN_SECRET` | Modal.com settings |

**Environment-scoped** (same values for `production` and `staging`):

| Secret | Source |
|--------|--------|
| `GCP_SERVICE_ACCOUNT` | `github-deploy@PROJECT.iam.gserviceaccount.com` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/NUMBER/locations/global/workloadIdentityPools/github-actions/providers/github` |

**Repo-level variables:**

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | `policyengine-api-v2-alpha` |
| `GCP_REGION` | `us-central1` |
| `PROJECT_NAME` | `policyengine-api-v2-alpha` |
| `API_SERVICE_NAME` | `policyengine-api-v2-alpha-api` |

### Deployment Pipeline

After setup, merging to main triggers:

```
test → migrate/build/infra/setup-modal (parallel)
     → deploy staging (Modal + Cloud Run tagged revision)
     → integration tests against staging
     → deploy production (canary + health check + traffic shift)
```

To bypass staging for urgent hotfixes, trigger `deploy.yml` via `workflow_dispatch` with `skip_staging=true`.

### Rollback

Cloud Run keeps previous revisions:

```bash
gcloud run revisions list --service=policyengine-api-v2-alpha-api --region=us-central1
gcloud run services update-traffic policyengine-api-v2-alpha-api \
  --region=us-central1 --to-revisions=REVISION_NAME=100
```

## Key Files

| File | Purpose |
|------|---------|
| `.env.example` | All environment variables with descriptions |
| `Makefile` | Local development targets |
| `docker-compose.yml` | Local API service definition |
| `terraform/main.tf` | Cloud Run, Artifact Registry, IAM |
| `terraform/variables.tf` | Terraform input variables |
| `.github/workflows/deploy.yml` | Full deploy pipeline (staging + production) |
| `.github/workflows/test.yml` | PR checks (lint, tests, OpenAPI diff) |
| `.github/workflows/versioning.yml` | Version bump + changelog + GitHub Release |
| `.github/scripts/` | Helper scripts for Modal environments, secrets, health checks |
| `scripts/init.py` | Database initialization (migrations + RLS + storage) |
| `scripts/seed.py` | Data seeding (models, variables, parameters, datasets) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `supabase start` fails | Ensure Docker is running; try `supabase stop && docker system prune -f` |
| Migration lock timeout | Production has long-running queries; retry during low traffic |
| Terraform state locked | `cd terraform && terraform force-unlock <LOCK_ID>` |
| Modal secrets not found | Check environment: `modal secret list --env=main` |
| Permission denied on deploy | Service account missing IAM role (see Step 3 in runbook) |

## Additional Resources

### Reference Files

- **`references/runbook.md`** — Complete step-by-step setup guide with exact commands for GCP, WIF, Supabase, Modal, and GitHub configuration

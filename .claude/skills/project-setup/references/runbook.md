# Setup Runbook

Complete guide to setting up the PolicyEngine API v2 for local development and production deployment.

## Part 1: Local Development

### Prerequisites

Install these tools before starting:

| Tool | Install | Purpose |
|------|---------|---------|
| **uv** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Python package manager |
| **Supabase CLI** | `brew install supabase/tap/supabase` | Local Postgres + storage |
| **Docker** | [docker.com](https://docs.docker.com/get-docker/) | Container runtime |
| **Modal CLI** | `pip install modal` then `modal setup` | Serverless compute (optional) |

### Step 1: Clone and install

```bash
git clone https://github.com/PolicyEngine/policyengine-api-v2-alpha.git
cd policyengine-api-v2-alpha
make install    # uv pip install -e .
```

### Step 2: Configure environment

```bash
cp .env.example .env
```

The defaults in `.env.example` work for local development with Supabase. You only need to fill in:

| Variable | Where to get it | Required? |
|----------|----------------|-----------|
| `SUPABASE_KEY` | Output of `supabase start` (anon key) | Yes |
| `SUPABASE_SERVICE_KEY` | Output of `supabase start` (service_role key) | Yes |
| `HUGGING_FACE_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | For seeding datasets |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | For `/agent` endpoint only |
| `LOGFIRE_TOKEN` | [logfire.pydantic.dev](https://logfire.pydantic.dev) | Optional (observability) |

### Step 3: Start Supabase

```bash
supabase start
```

This starts local Postgres (port 54322), PostgREST (port 54321), and storage. Copy the `anon key` and `service_role key` from the output into your `.env`.

### Step 4: Initialize database

```bash
make init    # runs Alembic migrations + creates storage bucket + applies RLS policies
```

This is idempotent and safe to re-run. To wipe and recreate:

```bash
uv run python scripts/init.py --reset
```

### Step 5: Seed data

```bash
make seed         # lite mode: both countries, 2026 datasets, core regions (~5 min)
make seed-full    # full mode: all years, all parameters, all regions (~30 min)
```

Requires `HUGGING_FACE_TOKEN` to download population datasets.

### Step 6: Start the API

```bash
make dev    # docker compose up — starts FastAPI at http://localhost:8000
```

The API is available at:
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- OpenAPI schema: `http://localhost:8000/openapi.json`

### Step 7: Deploy Modal functions (optional)

Needed only if you want to run simulations (household calculations, economy comparisons):

```bash
modal setup                    # authenticate with Modal.com (one-time)
make modal-deploy              # deploy serverless functions
# or for local testing:
make modal-serve               # run Modal functions locally
```

### Common local workflows

```bash
make test             # run unit tests
make integration-test # full integration test (starts Supabase, inits, seeds, tests)
make format           # ruff format
make lint             # ruff lint with auto-fix
make rebuild          # full Docker rebuild (down → build --no-cache → up)
make db-reset-local   # drop everything, recreate, reseed lite
make db-reseed-local  # keep tables, reseed lite
make logs             # docker compose logs -f
```

---

## Part 2: Production Deployment

Production runs on GCP Cloud Run (API) + Modal.com (compute) + Supabase (database). Deployment is fully automated via GitHub Actions after the one-time infrastructure setup below.

### One-time setup checklist

- [ ] GCP project created
- [ ] GCP APIs enabled
- [ ] Terraform state bucket created
- [ ] Service account for GitHub Actions created
- [ ] Workload Identity Federation configured
- [ ] Supabase project created
- [ ] Modal.com account and token created
- [ ] GitHub secrets and variables configured
- [ ] GitHub environments created (production, staging)

### Step 1: GCP project

Create a GCP project (or use an existing one). The project ID is used throughout — this repo uses `policyengine-api-v2-alpha`.

Enable required APIs:

```bash
gcloud config set project policyengine-api-v2-alpha

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com
```

### Step 2: Terraform state bucket

Terraform stores infrastructure state in a GCS bucket. Create it once:

```bash
gcloud storage buckets create gs://policyengine-api-v2-alpha-terraform \
  --location=us-central1 \
  --uniform-bucket-level-access

gcloud storage buckets update gs://policyengine-api-v2-alpha-terraform \
  --versioning
```

The bucket name must match `terraform/main.tf`:

```hcl
backend "gcs" {
  bucket = "policyengine-api-v2-alpha-terraform"
  prefix = "terraform/state"
}
```

### Step 3: GitHub Actions service account

Create a service account that GitHub Actions uses to deploy:

```bash
# Create service account
gcloud iam service-accounts create github-deploy \
  --display-name="GitHub Actions deploy"

# Grant roles
PROJECT_ID=policyengine-api-v2-alpha
SA_EMAIL=github-deploy@${PROJECT_ID}.iam.gserviceaccount.com

for ROLE in \
  roles/run.admin \
  roles/artifactregistry.admin \
  roles/iam.serviceAccountUser \
  roles/storage.admin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE"
done
```

Required roles:
| Role | Purpose |
|------|---------|
| `roles/run.admin` | Deploy and manage Cloud Run services |
| `roles/artifactregistry.admin` | Push Docker images |
| `roles/iam.serviceAccountUser` | Act as the Cloud Run service account |
| `roles/storage.admin` | Manage Terraform state bucket |

### Step 4: Workload Identity Federation

WIF lets GitHub Actions authenticate to GCP without storing a service account key. This is the recommended approach — no long-lived credentials.

```bash
PROJECT_ID=policyengine-api-v2-alpha
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SA_EMAIL=github-deploy@${PROJECT_ID}.iam.gserviceaccount.com

# Create workload identity pool
gcloud iam workload-identity-pools create github-actions \
  --location=global \
  --display-name="GitHub Actions"

# Create OIDC provider for GitHub
gcloud iam workload-identity-pools providers create-oidc github \
  --location=global \
  --workload-identity-pool=github-actions \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'PolicyEngine/policyengine-api-v2-alpha'"

# Allow GitHub Actions to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/attribute.repository/PolicyEngine/policyengine-api-v2-alpha"
```

After this, note two values for GitHub secrets:

```
GCP_SERVICE_ACCOUNT = github-deploy@policyengine-api-v2-alpha.iam.gserviceaccount.com

GCP_WORKLOAD_IDENTITY_PROVIDER = projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-actions/providers/github
```

You can retrieve the provider resource name later with:

```bash
gcloud iam workload-identity-pools providers describe github \
  --location=global \
  --workload-identity-pool=github-actions \
  --format='value(name)'
```

### Step 5: Supabase project

Create a Supabase project at [supabase.com](https://supabase.com). From the dashboard (Settings > API / Database), collect:

| Value | Where | GitHub secret |
|-------|-------|---------------|
| Project URL | Settings > API > URL | `SUPABASE_URL` |
| Anon key | Settings > API > anon/public | `SUPABASE_KEY` |
| Connection string | Settings > Database > Connection string (URI) | `SUPABASE_DB_URL` |

Use the **direct connection** (port 5432) for `SUPABASE_DB_URL`, not the connection pooler. Alembic migrations require direct connections for DDL.

### Step 6: Modal.com

1. Create account at [modal.com](https://modal.com)
2. Generate API token: Settings > API Tokens > Create new token
3. Note the `Token ID` and `Token Secret` for GitHub secrets

Modal secrets (database credentials etc.) are synced automatically by the deploy pipeline via `.github/scripts/modal-sync-secrets.sh`.

### Step 7: Logfire (optional)

Create account at [logfire.pydantic.dev](https://logfire.pydantic.dev). Create a project and note the write token for `LOGFIRE_TOKEN`.

### Step 8: GitHub secrets and variables

**Repo-level secrets** (Settings > Secrets and variables > Actions > Secrets):

```bash
gh secret set SUPABASE_URL        # Supabase project URL
gh secret set SUPABASE_KEY        # Supabase anon key
gh secret set SUPABASE_DB_URL     # PostgreSQL direct connection string
gh secret set LOGFIRE_TOKEN       # Logfire write token
gh secret set MODAL_TOKEN_ID      # Modal API token ID
gh secret set MODAL_TOKEN_SECRET  # Modal API token secret
```

**Environment-scoped secrets** (same values for both `production` and `staging`):

```bash
# Production
gh secret set GCP_SERVICE_ACCOUNT --env production
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --env production

# Staging
gh secret set GCP_SERVICE_ACCOUNT --env staging
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --env staging
```

**Repo-level variables** (Settings > Secrets and variables > Actions > Variables):

```bash
gh variable set GCP_PROJECT_ID    --body "policyengine-api-v2-alpha"
gh variable set GCP_REGION        --body "us-central1"
gh variable set PROJECT_NAME      --body "policyengine-api-v2-alpha"
gh variable set API_SERVICE_NAME  --body "policyengine-api-v2-alpha-api"
```

### Step 9: GitHub environments

Create two environments in Settings > Environments:

| Environment | Purpose | Protection rules |
|-------------|---------|-----------------|
| `production` | Production deploys | Optional: required reviewers |
| `staging` | Staging deploys (pre-prod validation) | None needed |

Both environments need `GCP_SERVICE_ACCOUNT` and `GCP_WORKLOAD_IDENTITY_PROVIDER` secrets (same values — they deploy to the same GCP project).

### Step 10: Custom domain (optional)

Map a custom domain to the Cloud Run service:

```bash
gcloud beta run domain-mappings create \
  --service=policyengine-api-v2-alpha-api \
  --domain=v2.api.policyengine.org \
  --region=us-central1
```

Follow the DNS verification instructions from the output.

---

## How deployment works

After the one-time setup, deployment is fully automated:

1. **PR opened** — `test.yml` runs: lint, format check, unit tests, OpenAPI schema diff, changelog fragment check
2. **PR merged to main** — `deploy.yml` runs:
   - Test (unit tests)
   - Parallel: migrate database, build Docker image, apply Terraform, setup Modal environments
   - Deploy to staging (Modal + Cloud Run tagged revision)
   - Integration tests against staging URL
   - Deploy to production (canary with health check, then shift traffic)
3. **Changelog fragments merged** — `versioning.yml` runs: bump version, build changelog, create git tag + GitHub Release

### Skip staging

For urgent fixes, trigger `deploy.yml` via workflow_dispatch with `skip_staging=true` to deploy directly to production.

### Rollback

Cloud Run keeps previous revisions. To rollback:

```bash
# List revisions
gcloud run revisions list --service=policyengine-api-v2-alpha-api --region=us-central1

# Route traffic to previous revision
gcloud run services update-traffic policyengine-api-v2-alpha-api \
  --region=us-central1 \
  --to-revisions=REVISION_NAME=100
```

---

## Troubleshooting

### "Permission denied" on deploy

The GitHub Actions service account is missing a role. Check Step 3 for required roles.

### Terraform state lock

If a previous Terraform run crashed, the state may be locked:

```bash
cd terraform
terraform force-unlock <LOCK_ID>
```

### Modal secrets not found

Modal secrets are environment-scoped. Make sure you're deploying to the right environment:

```bash
modal secret list --env=main      # production
modal secret list --env=staging   # staging
```

### Database migration fails in CI

Check `alembic/env.py` — it sets `lock_timeout=5000` (5s). If production has long-running queries holding locks, the migration will fail fast rather than queue. Retry after the queries complete, or run during low-traffic periods.

### Supabase start fails

Docker must be running. If ports conflict:

```bash
supabase stop
docker system prune -f
supabase start
```

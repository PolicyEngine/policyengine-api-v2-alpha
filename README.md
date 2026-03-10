# PolicyEngine API v2

FastAPI service for UK and US tax-benefit microsimulations. Uses Supabase for storage and Modal.com for serverless compute with sub-1s cold starts.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Level 2: Reports (future)                                  │
│  AI-generated documents, orchestrating multiple jobs        │
├─────────────────────────────────────────────────────────────┤
│  Level 1: Analyses                                          │
│  Operations on simulations (comparisons, aggregations)      │
│  /analysis/economic-impact → economy_comparison_*           │
├─────────────────────────────────────────────────────────────┤
│  Level 0: Simulations                                       │
│  Single world-state calculations                            │
│  /household/calculate → simulate_household_*                │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│      Modal.com           │
│  simulate_household_uk   │
│  simulate_household_us   │
│  economy_comparison_uk   │──▶ Supabase
│  economy_comparison_us   │
└──────────────────────────┘
```

All compute runs on Modal.com serverless functions. The API triggers these functions and clients poll for results. See [docs/DESIGN.md](docs/DESIGN.md) for the full API hierarchy design.

## Quick start

### Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Docker and Docker Compose
- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- [Modal.com](https://modal.com) account (optional — only needed for running simulations)

### Local development

```bash
make install                  # install dependencies
cp .env.example .env          # create env file
supabase start                # start local supabase (copy anon/service keys to .env)
make init                     # create tables, storage bucket, RLS policies
make seed                     # seed UK/US models with variables, parameters, datasets
make dev                      # start API at http://localhost:8000
```

### Running configurations

The API can run in several configurations depending on what you need:

| Configuration | What works | Setup |
|---------------|-----------|-------|
| **API only** (no Modal) | Metadata endpoints (`/parameters`, `/variables`, `/datasets`, `/policies`, `/health`) | Steps above, skip Modal |
| **API + Modal local** | Everything, Modal functions run on your machine | Add `make modal-serve` |
| **API + Modal deployed** | Everything, Modal functions run on Modal.com | Add `make modal-deploy` |
| **Full stack** | Everything + agent endpoint | Add `ANTHROPIC_API_KEY` to `.env` |

To connect Modal:

```bash
modal setup                   # authenticate with Modal.com (one-time)
make modal-serve              # run Modal functions locally (for development)
# or
make modal-deploy             # deploy to Modal.com (for production-like testing)
```

### Seeding options

```bash
make seed                     # lite mode: both countries, 2026 datasets (~5 min)
make seed-full                # full mode: all years, all parameters, all regions (~30 min)
```

Both require `HUGGING_FACE_TOKEN` in `.env` for downloading population datasets.

For the full setup guide covering production deployment, GCP, Terraform, WIF, GitHub secrets, and CI/CD, see [docs/SETUP_RUNBOOK.md](docs/SETUP_RUNBOOK.md).

> **Using Claude Code?** Ask `/project-setup` for interactive guidance on local development or production deployment.

## API reference

All simulation and analysis endpoints are async: submit a request, get a job ID, poll until complete.

### Household simulations

Calculate taxes and benefits for a single household.

**Submit (UK):**

```bash
curl -X POST http://localhost:8000/household/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "people": [{"age": 30, "employment_income": 50000}],
    "year": 2026
  }'
```

**Submit (US):**

```bash
curl -X POST http://localhost:8000/household/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_us",
    "people": [{"age": 40, "employment_income": 70000}],
    "tax_unit": {"state_code": "CA"},
    "year": 2024
  }'
```

**Poll:**

```bash
curl http://localhost:8000/household/calculate/{job_id}
```

Response (when complete):

```json
{
  "job_id": "...",
  "status": "completed",
  "result": {
    "person": [{"income_tax": 7500, "national_insurance": 4500, "...": "..."}],
    "household": {"household_net_income": 38000, "...": "..."}
  }
}
```

### Economy comparison analysis

Compare baseline vs reform across a population dataset. Returns decile impacts, budget impacts, and winners/losers.

**Submit:**

```bash
curl -X POST http://localhost:8000/analysis/economic-impact \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "dataset_id": "...",
    "policy_id": "..."
  }'
```

**Poll:**

```bash
curl http://localhost:8000/analysis/economic-impact/{job_id}
```

Response (when complete):

```json
{
  "report_id": "...",
  "status": "completed",
  "decile_impacts": ["..."],
  "program_statistics": ["..."]
}
```

### Policies

Create policy reforms by specifying parameter changes.

```bash
# Search for parameters
curl "http://localhost:8000/parameters?search=basic_rate"

# Create policy
curl -X POST http://localhost:8000/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lower basic rate to 16p",
    "parameter_values": [{
      "parameter_id": "...",
      "value_json": 0.16,
      "start_date": "2026-01-01T00:00:00Z"
    }]
  }'
```

### Other endpoints

```
GET  /datasets                List population datasets
GET  /parameters?search=...   Search parameters
POST /dynamics                Create behavioural response
GET  /variables               List variables
GET  /health                  Health check
```

## Environment variables

Copy `.env.example` to `.env` and configure. All variables are documented in `.env.example`.

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase API URL | Yes |
| `SUPABASE_KEY` | Supabase anon/public key | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Yes |
| `SUPABASE_DB_URL` | PostgreSQL connection string | Yes |
| `STORAGE_BUCKET` | Supabase storage bucket name | Yes (default: `datasets`) |
| `HUGGING_FACE_TOKEN` | HuggingFace token for dataset downloads | For seeding |
| `ANTHROPIC_API_KEY` | Anthropic API key for agent endpoint | For `/agent` only |
| `AGENT_USE_MODAL` | Use Modal for agent compute (`true`/`false`) | No (default: `false`) |
| `MODAL_ENVIRONMENT` | Modal environment (`main`, `staging`) | No (default: `main`) |
| `LOGFIRE_TOKEN` | Logfire observability token | No |

For production Modal deployment, secrets are managed via Modal CLI (not `.env`):

```bash
modal secret create policyengine-db DATABASE_URL='...' SUPABASE_URL='...' ...
modal secret create anthropic-api-key ANTHROPIC_API_KEY='...'
```

## Development

```bash
make format           # ruff formatting
make lint             # ruff linting with auto-fix
make test             # unit tests
make integration-test # full integration tests (starts Supabase, inits, seeds, tests)
make db-reset-local   # drop everything, recreate, reseed
make db-reseed-local  # keep tables, reseed
make logs             # docker compose logs
```

## Deployment

### Modal.com (compute)

```bash
make modal-deploy     # deploy serverless functions to production
make modal-serve      # run Modal functions locally
```

### Cloud Run (API)

Automated via GitHub Actions on merge to main. The pipeline runs:

```
test → migrate/build/infra/setup-modal (parallel)
     → deploy staging (tagged revision, no traffic)
     → integration tests against staging
     → deploy production (canary + health check + traffic shift)
```

See [docs/SETUP_RUNBOOK.md](docs/SETUP_RUNBOOK.md) for production infrastructure setup.

> **Using Claude Code?** Ask `/project-setup` for interactive guidance, or `/database-deployment-pipeline` for details on how schema changes reach production.

## Project structure

```
policyengine-api-v2/
├── src/policyengine_api/
│   ├── api/              # FastAPI routers
│   ├── models/           # SQLModel database models
│   ├── services/         # Database, storage
│   ├── modal_app.py      # Modal serverless functions
│   └── main.py           # FastAPI app
├── supabase/migrations/  # RLS policies
├── terraform/            # Cloud Run infrastructure
├── scripts/              # Database init and seeding
├── docs/                 # Next.js docs site + DESIGN.md
└── .claude/skills/       # Claude Code skills (project-setup, database-deployment-pipeline)
```

## Licence

AGPL-3.0

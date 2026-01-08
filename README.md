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
- [Modal.com](https://modal.com) account

### Local development

```bash
make install                  # install dependencies
cp .env.example .env          # create env file
supabase start                # start local supabase (copy anon/service keys to .env)
make init                     # create tables, storage bucket, RLS policies
make seed                     # seed UK/US models with variables, parameters, datasets
docker compose up             # start API at http://localhost:8000
```

To run simulations, deploy Modal functions:

```bash
modal token set --token-id <id> --token-secret <secret>
make modal-deploy
```

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
    "person": [{"income_tax": 7500, "national_insurance": 4500, ...}],
    "household": {"household_net_income": 38000, ...}
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
  "decile_impacts": [...],
  "program_statistics": [...]
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

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase API URL (https://...) |
| `SUPABASE_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `SUPABASE_DB_URL` | PostgreSQL connection string |
| `STORAGE_BUCKET` | Supabase storage bucket name |
| `LOGFIRE_TOKEN` | Logfire observability token |
| `ANTHROPIC_API_KEY` | Anthropic API key for agent |
| `AGENT_USE_MODAL` | Use Modal for agent (true/false) |

For production Modal deployment, secrets are managed via Modal CLI (not .env):
```bash
modal secret create policyengine-db DATABASE_URL='...' SUPABASE_URL='...' ...
modal secret create anthropic-api-key ANTHROPIC_API_KEY='...'
```

## Development

```bash
make format           # ruff formatting
make lint             # ruff linting with auto-fix
make test             # unit tests
make integration-test # full integration tests
```

## Deployment

### Modal.com (compute)

```bash
make modal-deploy     # deploy serverless functions
```

### Cloud Run (API)

Automated via GitHub Actions on merge to main. The Docker build compiles the Next.js docs site and bundles it into the API image, served at `/docs`.

Required GitHub secrets:
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_DB_URL`
- `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`
- `LOGFIRE_TOKEN`
- GCP workload identity federation

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
└── docs/                 # Next.js docs site + DESIGN.md
```

## Licence

AGPL-3.0

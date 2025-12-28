# PolicyEngine API v2

FastAPI service for UK and US tax-benefit microsimulations. Uses Supabase for storage and Modal.com for serverless compute with sub-1s cold starts.

## Architecture

```
┌─────────────────┐         ┌──────────────────────────┐
│  FastAPI API    │────────▶│      Modal.com           │
│  (Cloud Run)    │         │                          │
│                 │         │  calculate_household_uk  │
│  /household/*   │─trigger─│  calculate_household_us  │
│  /analysis/*    │─trigger─│  run_report_uk           │──▶ Supabase
│                 │         │  run_report_us           │
└─────────────────┘         └──────────────────────────┘
```

All compute-intensive operations (household calculations, economic impact analysis) run on Modal.com serverless functions. The API triggers these functions and clients poll for results.

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

All simulation endpoints are async: submit a request, get a job/report ID, poll until complete.

### Household calculations

Calculate taxes and benefits for a single household. Results include all computed variables for each person and entity.

**Request structure (UK):**

```json
{
  "tax_benefit_model_name": "policyengine_uk",
  "people": [{"age": 30, "employment_income": 50000}],
  "benunit": {},
  "household": {},
  "year": 2026,
  "policy_id": null,
  "dynamic_id": null
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `tax_benefit_model_name` | Yes | `policyengine_uk` or `policyengine_us` |
| `people` | Yes | Array of person objects with variable values (flat values, not `{"2024": value}`) |
| `benunit` | No | UK benefit unit variables (ignored for US) |
| `household` | No | Household-level variables |
| `year` | No | Simulation year. Default: 2026 (UK), 2024 (US) |
| `policy_id` | No | UUID of policy reform to apply |
| `dynamic_id` | No | UUID of behavioural response specification |

**Request structure (US):**

```json
{
  "tax_benefit_model_name": "policyengine_us",
  "people": [{"age": 40, "employment_income": 70000}],
  "tax_unit": {"state_code": "CA"},
  "household": {"state_fips": 6},
  "marital_unit": {},
  "family": {},
  "spm_unit": {},
  "year": 2024,
  "policy_id": null,
  "dynamic_id": null
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `tax_benefit_model_name` | Yes | `policyengine_us` |
| `people` | Yes | Array of person objects |
| `tax_unit` | No | Tax unit variables (e.g. `state_code` for state) |
| `household` | No | Household variables (e.g. `state_fips` for state) |
| `marital_unit` | No | Marital unit variables |
| `family` | No | Family variables |
| `spm_unit` | No | SPM unit variables |
| `year` | No | Simulation year. Default: 2024 |
| `policy_id` | No | UUID of policy reform |
| `dynamic_id` | No | UUID of behavioural response |

**Submit a calculation:**

```bash
curl -X POST http://localhost:8000/household/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "people": [{"age": 30, "employment_income": 50000}],
    "year": 2026
  }'
```

Response:
```json
{"job_id": "abc123-...", "status": "pending"}
```

**Poll for results:**

```bash
curl http://localhost:8000/household/calculate/abc123-...
```

Response (when complete):
```json
{
  "job_id": "abc123-...",
  "status": "completed",
  "result": {
    "person": [{"income_tax": 7500, "national_insurance": 4500, ...}],
    "household": {"household_net_income": 38000, ...}
  },
  "error_message": null
}
```

Status values: `pending`, `running`, `completed`, `failed`

### Household impact comparison

Compare a household under baseline (current law) vs reform (with policy_id). Returns both calculations plus computed differences.

**Submit:**

```bash
curl -X POST http://localhost:8000/household/impact \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "people": [{"age": 30, "employment_income": 50000}],
    "year": 2026,
    "policy_id": "uuid-of-reform-policy"
  }'
```

**Poll:**

```bash
curl http://localhost:8000/household/impact/abc123-...
```

Response (when complete):
```json
{
  "job_id": "abc123-...",
  "status": "completed",
  "baseline_result": {"person": [...], "household": {...}},
  "reform_result": {"person": [...], "household": {...}},
  "impact": {
    "household": {
      "household_net_income": {"baseline": 38000, "reform": 39200, "change": 1200}
    },
    "person": [{"income_tax": {"baseline": 7500, "reform": 6500, "change": -1000}}]
  }
}
```

### Economic impact analysis

Run economy-wide analysis comparing baseline vs reform across a population dataset. Returns distributional impacts (by income decile) and program statistics (tax/benefit totals).

**Submit:**

```bash
curl -X POST http://localhost:8000/analysis/economic-impact \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "dataset_id": "uuid-from-datasets-endpoint",
    "policy_id": "uuid-of-reform-policy"
  }'
```

| Field | Required | Description |
|-------|----------|-------------|
| `tax_benefit_model_name` | Yes | `policyengine_uk` or `policyengine_us` |
| `dataset_id` | Yes | UUID from GET /datasets |
| `policy_id` | No | UUID of policy reform (null = baseline only) |
| `dynamic_id` | No | UUID of behavioural response specification |

**Poll:**

```bash
curl http://localhost:8000/analysis/economic-impact/report-uuid-...
```

Response (when complete):
```json
{
  "report_id": "...",
  "status": "completed",
  "baseline_simulation": {"id": "...", "status": "completed"},
  "reform_simulation": {"id": "...", "status": "completed"},
  "decile_impacts": [
    {"decile": 1, "baseline_mean": 15000, "reform_mean": 15500, "relative_change": 0.033, ...},
    ...
  ],
  "program_statistics": [
    {"program_name": "income_tax", "baseline_total": 200000000000, "reform_total": 180000000000, "change": -20000000000, ...},
    ...
  ]
}
```

### Policies

Create policy reforms by specifying parameter changes.

**Search for parameters:**

```bash
curl "http://localhost:8000/parameters?search=basic_rate"
```

**Create a policy:**

```bash
curl -X POST http://localhost:8000/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lower basic rate to 16p",
    "description": "Reduce UK basic income tax rate from 20% to 16%",
    "parameter_values": [
      {
        "parameter_id": "uuid-from-parameters-search",
        "value_json": 0.16,
        "start_date": "2026-01-01T00:00:00Z",
        "end_date": null
      }
    ]
  }'
```

**List policies:**

```bash
curl http://localhost:8000/policies
```

**Get policy:**

```bash
curl http://localhost:8000/policies/uuid-...
```

### Datasets

List available population datasets for economic impact analysis.

```bash
curl http://localhost:8000/datasets
```

UK datasets contain "uk" or "frs" in the name. US datasets contain "us" or "cps".

### Dynamics

Create behavioural response specifications (labour supply elasticities, etc).

```bash
curl -X POST http://localhost:8000/dynamics \
  -H "Content-Type: application/json" \
  -d '{"name": "Standard elasticities", "description": "Default labour supply responses"}'
```

### Other endpoints

```
GET  /parameters              List/search policy parameters
GET  /parameters/{id}         Get parameter details
GET  /parameter-values        List parameter values
GET  /variables               List simulation variables
GET  /variables/{id}          Get variable details
GET  /tax-benefit-models      List models (UK, US)
GET  /tax-benefit-model-versions  List model versions
GET  /health                  Health check
```

## Complete workflow example

Analyse the impact of lowering UK basic income tax rate to 16%:

```bash
# 1. Find the parameter
curl "http://localhost:8000/parameters?search=basic_rate" | jq '.[] | {id, name}'

# 2. Create policy reform
curl -X POST http://localhost:8000/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lower basic rate to 16p",
    "parameter_values": [{
      "parameter_id": "<id-from-step-1>",
      "value_json": 0.16,
      "start_date": "2026-01-01T00:00:00Z"
    }]
  }'
# Note the policy_id from response

# 3. Test on a household
curl -X POST http://localhost:8000/household/impact \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "people": [{"age": 40, "employment_income": 50000}],
    "year": 2026,
    "policy_id": "<policy-id-from-step-2>"
  }'
# Note job_id, poll until complete

# 4. Get a dataset for population analysis
curl http://localhost:8000/datasets | jq '.[] | select(.name | contains("uk")) | {id, name}'

# 5. Run economy-wide analysis
curl -X POST http://localhost:8000/analysis/economic-impact \
  -H "Content-Type: application/json" \
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "dataset_id": "<dataset-id>",
    "policy_id": "<policy-id>"
  }'
# Note report_id, poll until complete

# 6. Poll for results
curl http://localhost:8000/analysis/economic-impact/<report-id>
```

## Development

```bash
make format           # ruff formatting
make lint             # ruff linting with auto-fix
make test             # unit tests
make integration-test # full integration tests
```

## Database

```bash
make init             # reset and create tables/storage
make seed             # seed UK/US models
make db-reset-prod    # reset production (requires confirmation)
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
└── docs/                 # Next.js documentation site
```

## Licence

AGPL-3.0

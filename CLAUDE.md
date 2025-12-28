# PolicyEngine API v2

FastAPI backend for tax-benefit policy microsimulations using PolicyEngine's UK and US models.

## How it works

1. Client submits calculation request to FastAPI (Cloud Run)
2. API creates a job record in Supabase and triggers Modal.com function
3. Modal function runs calculation with pre-loaded PolicyEngine models (sub-1s cold start)
4. Modal writes results directly to Supabase
5. Client polls API until job status = "completed"

## Tech stack

- **Framework:** FastAPI with async endpoints
- **Database:** Supabase (Postgres) via SQLModel
- **Compute:** Modal.com serverless functions
- **Package manager:** UV
- **Formatting:** Ruff
- **Testing:** Pytest with pytest-asyncio
- **Deployment:** Terraform on GCP Cloud Run

## Development

```bash
make install          # install dependencies with uv
make dev              # start supabase + api via docker compose
make test             # run unit tests
make integration-test # full integration tests
make format           # ruff formatting
make lint             # ruff linting with auto-fix
make modal-deploy     # deploy Modal.com serverless functions
```

## Project structure

- `src/policyengine_api/api/` - FastAPI routers
- `src/policyengine_api/models/` - SQLModel database models
- `src/policyengine_api/services/` - database and storage services
- `src/policyengine_api/modal_app.py` - Modal.com serverless functions
- `supabase/migrations/` - SQL migrations
- `terraform/` - GCP Cloud Run infrastructure
- `docs/` - Next.js documentation site (bundled into API image at /docs)

## Key patterns

SQLModel for database schemas, Pydantic BaseModel for request/response schemas. All calculation endpoints are async (submit job → poll for results). Modal functions use Supabase connection pooler for IPv4 compatibility.

## Deployment

Never commit directly to main. PRs trigger tests; merging to main deploys to Cloud Run via Terraform.

Use `gh` CLI for GitHub operations to ensure Actions run correctly.

## Database

`make init` resets tables and storage. `make seed` populates UK/US models with variables, parameters, and datasets.

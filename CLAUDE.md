# PolicyEngine API v2

FastAPI backend for tax-benefit policy microsimulations using PolicyEngine's UK and US models.

## API hierarchy

```
Level 2: Reports        AI-generated documents (future)
Level 1: Analyses       Operations on simulations (economy_comparison_*)
Level 0: Simulations    Single world-state calculations (simulate_household_*)
```

See [docs/DESIGN.md](docs/DESIGN.md) for the full design including future endpoints.

## How it works

1. Client submits request to FastAPI (Cloud Run)
2. API creates job record in Supabase and triggers Modal.com function
3. Modal runs calculation with pre-loaded PolicyEngine models (sub-1s cold start)
4. Modal writes results directly to Supabase
5. Client polls API until job status = "completed"

## Modal functions

| Function | Purpose |
|----------|---------|
| `simulate_household_uk` | Single UK household calculation |
| `simulate_household_us` | Single US household calculation |
| `economy_comparison_uk` | UK economy comparison (decile impacts, budget impact) |
| `economy_comparison_us` | US economy comparison |

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
- `docs/` - Next.js docs site + DESIGN.md

## Key patterns

SQLModel for database schemas, Pydantic BaseModel for request/response schemas. All calculation endpoints are async (submit job → poll for results). Modal functions use Supabase connection pooler for IPv4 compatibility. Analysis logic lives in `policyengine` package; API is thin orchestration layer.

## Deployment

Never commit directly to main. PRs trigger tests; merging to main deploys to Cloud Run via Terraform.

Use `gh` CLI for GitHub operations to ensure Actions run correctly.

## Database

`make init` resets tables and storage. `make seed` populates UK/US models with variables, parameters, and datasets.

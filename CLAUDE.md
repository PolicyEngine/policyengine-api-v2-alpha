# PolicyEngine API v2

FastAPI backend for tax-benefit policy microsimulations using PolicyEngine's UK and US models. Provides endpoints for running simulations, comparing policy reforms, and aggregating results.

## Tech stack

- **Framework:** FastAPI with async endpoints
- **Database:** Supabase (Postgres) with SQLModel ORM
- **Package manager:** UV (not pip)
- **Formatting:** Ruff (not black)
- **Testing:** Pytest with pytest-asyncio
- **Deployment:** Terraform on GCP Cloud Run

## Development

```bash
make install          # install dependencies with uv
make dev              # start supabase + api + worker via docker compose
make test             # run unit tests
make integration-test # full integration tests
make format           # ruff formatting
make lint             # ruff linting with auto-fix
```

Local development uses docker compose with a local Supabase instance. Copy `.env.example` to `.env` for local config.

## Project structure

- `src/policyengine_api/api/` - FastAPI routers (14 endpoint groups)
- `src/policyengine_api/models/` - SQLModel database models
- `src/policyengine_api/services/` - database and storage services
- `src/policyengine_api/tasks/` - background worker for async simulations
- `supabase/migrations/` - SQL migrations for RLS and Postgres features
- `terraform/` - GCP Cloud Run infrastructure
- `docs/` - Next.js documentation site

## Key patterns

SQLModel defines all database schemas. Use Pydantic BaseModel for request/response schemas and BaseSettings for configuration. All API endpoints should be async functions.

The background worker processes simulations asynchronously. Clients poll simulation status until complete.

MCP server exposes all endpoints as Claude tools via streamable HTTP transport.

## Testing

Run `make test` before committing. Unit tests use in-memory SQLite fixtures for speed. Integration tests require a running Supabase instance.

## Deployment

Never commit directly to main. Use PRs with passing tests. GitHub Actions runs tests on PRs, then deploys to Cloud Run on merge to main via Terraform.

Use `gh` CLI for GitHub operations (not `git`) to ensure Actions run correctly.

## Database

Use `make init` to reset and create tables/storage. Use `make seed` to populate UK/US models with variables, parameters, and datasets. Production reset requires explicit confirmation.

## Observability

Logfire provides automatic instrumentation. Add tracing to complex async flows.

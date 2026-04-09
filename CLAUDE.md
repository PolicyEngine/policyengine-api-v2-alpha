# PolicyEngine API v2

FastAPI backend for tax-benefit policy microsimulations using PolicyEngine's UK and US models.

## API hierarchy

```
Level 2: Reports        AI-generated documents (future)
Level 1: Analyses       Operations on simulations (economy_comparison_*)
Level 0: Simulations    Single world-state calculations (simulate_household_*, simulate_economy_*)
```

See [docs/DESIGN.md](docs/DESIGN.md) for the full design including future endpoints.

## How it works

1. Client submits request to FastAPI (Cloud Run)
2. API resolves the country package version → versioned Modal app name via Modal Dicts
3. API creates job record in Supabase and spawns a function on the versioned Modal app
4. Modal runs calculation with pre-loaded PolicyEngine models (sub-1s cold start)
5. Modal writes results directly to Supabase
6. Client polls API until job status = "completed"

## Versioned Modal deployments

Each deploy creates a versioned Modal app named `policyengine-v2-us{X}-uk{Y}` (e.g., `policyengine-v2-us1-592-4-uk2-75-1`). Old versions remain deployed and accessible. Cloud Run routes to the correct version via v2-specific Modal Dict registries (`api-v2-us-versions`, `api-v2-uk-versions`).

**Key files:**
- `src/policyengine_api/modal/app.py` — Versioned app definition (dynamic name from env vars)
- `src/policyengine_api/modal/images.py` — Country images with exact version pins (`==`)
- `src/policyengine_api/modal/deploy.py` — Entry point for `modal deploy`
- `src/policyengine_api/version_resolver.py` — Resolves country+version to Modal app name
- `scripts/update_version_registry.py` — Updates Modal Dicts after deploy
- `.github/scripts/modal-deploy-versioned.sh` — Deploy script (generates app name, deploys, updates registry)

**Deploy:** `POLICYENGINE_US_VERSION=X POLICYENGINE_UK_VERSION=Y .github/scripts/modal-deploy-versioned.sh <environment>`

## Modal functions

| Function | Purpose |
|----------|---------|
| `simulate_household_uk` | Single UK household calculation |
| `simulate_household_us` | Single US household calculation |
| `simulate_economy_uk` | Single UK economy simulation |
| `simulate_economy_us` | Single US economy simulation |
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
- `src/policyengine_api/modal/` - Versioned Modal.com serverless functions
- `src/policyengine_api/version_resolver.py` - Version → Modal app name resolution
- `supabase/migrations/` - SQL migrations
- `terraform/` - GCP Cloud Run infrastructure
- `docs/` - Next.js docs site + DESIGN.md

## Key patterns

SQLModel for database schemas, Pydantic BaseModel for request/response schemas. All calculation endpoints are async (submit job → poll for results). Modal functions use Supabase connection pooler for IPv4 compatibility. Analysis logic lives in `policyengine` package; API is thin orchestration layer.

## Deployment

Never commit directly to main. PRs trigger tests; merging to main deploys to Cloud Run via Terraform.

Use `gh` CLI for GitHub operations to ensure Actions run correctly.

## Database

This project uses **Alembic** for database migrations. See `.claude/skills/database-migrations.md` for detailed guidelines.

**Key rules:**
- All schema changes go through Alembic migrations (never use `SQLModel.metadata.create_all()`)
- After modifying a model: `uv run alembic revision --autogenerate -m "Description"`
- Apply migrations: `uv run alembic upgrade head`

**Local development:**
```bash
supabase start                    # Start local Supabase
uv run python scripts/init.py     # Run migrations + apply RLS policies
uv run python scripts/seed.py     # Seed data
```

`scripts/init.py --reset` drops and recreates everything (destructive).

## Modal sandbox + Claude Code CLI gotchas

The agent endpoint (`/agent/stream`) runs Claude Code CLI inside a Modal sandbox. Hard-won lessons:

1. **Modal secrets must explicitly set env var names.** When creating: `modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-...`. Just having a secret named "anthropic-api-key" doesn't automatically set `ANTHROPIC_API_KEY`.

2. **`--dangerously-skip-permissions` doesn't work as root.** Modal containers run as root. Claude Code blocks this flag for security. Don't use it.

3. **`sb.exec()` doesn't close stdin.** This causes Claude to hang waiting for input. Wrap in shell: `sb.exec("sh", "-c", "claude ... < /dev/null 2>&1")`.

4. **Claude Code has first-run onboarding.** Pre-accept during image build:
   ```python
   .run_commands(
       "mkdir -p /root/.claude && "
       'echo \'{"hasCompletedOnboarding": true, "hasAcknowledgedCostThreshold": true}\' '
       "> /root/.claude/settings.json",
   )
   ```

5. **`--output-format stream-json` requires `--verbose`.** Otherwise you get an error.

6. **Modal image caching.** Changes to `.run_commands()` may not rebuild if earlier layers are cached. Add a cache-busting change (new env var, modified command) to force rebuild.

7. **Test locally before deploying.** Use `modal.Sandbox.create()` directly in a Python script to debug without waiting for Cloud Run deploys.

8. **MCP SSE doesn't work in Modal containers.** Claude Code with MCP works locally but exits immediately after init in Modal (both sandbox and function). Workaround implemented: `stream_policy_analysis` uses a system prompt with API documentation instead of MCP, and Claude makes direct HTTP calls via Bash/curl.

9. **`subprocess.Popen` needs `stdin=DEVNULL`.** Same issue as the sandbox - if stdin is left as a pipe (the default), Claude hangs waiting for input. Always use `stdin=subprocess.DEVNULL`.

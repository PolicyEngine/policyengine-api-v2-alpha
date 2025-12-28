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
2. API creates job record in Supabase and triggers Modal.com function
3. Modal runs calculation with pre-loaded PolicyEngine models (sub-1s cold start)
4. Modal writes results directly to Supabase
5. Client polls API until job status = "completed"

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

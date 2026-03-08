# Deployment Scaffolding Overview

How automated structures exist to deploy/update each component of the PolicyEngine v2 stack.

## 1. Supabase Database

**Schema:** Alembic migrations in `alembic/versions/`. Migrations run automatically in `deploy.yml` before the Cloud Run service is updated (`alembic upgrade head` against the direct Supabase connection). A 5-second `lock_timeout` is configured in `alembic/env.py` to prevent migrations from blocking production queries.

**RLS & Storage:** RLS policies and storage buckets are applied via `scripts/init.py` (idempotent SQL, outside Alembic). These are defense-in-depth only — the API connects as the `postgres` superuser via SQLAlchemy, which bypasses RLS. RLS only protects the Supabase PostgREST surface.

| Action | Trigger | Command |
|--------|---------|---------|
| Production migrations | Automatic (merge to main) | `alembic upgrade head` in `deploy.yml` |
| Local init | Manual | `make init` → migrations + RLS + storage bucket |
| Production reset | Manual workflow dispatch (`db-reset.yml`) | Requires typing `reset-prod`, has production approval gate |
| Seeding | Manual workflow dispatch or `make db-reseed-prod` | `scripts/seed.py --lite` or `--full` |

## 2. Modal Functions

**Source:** `modal_app.py` (household/economy simulations) and `agent_sandbox.py` (Claude Code CLI).

**Fully automated on merge to main** via `deploy.yml`:

1. Syncs GitHub Actions secrets → Modal (`modal secret create ... --force`)
2. Deploys both apps (`modal deploy`)
3. Validates secrets by calling `validate_secrets()` remotely

Also available locally: `make modal-deploy`.

**Note:** The Modal image installs `policyengine.py` from the `app-v2-migration` git branch, not PyPI. Updating the package requires redeploying Modal.

## 3. API (Cloud Run)

**Infrastructure:** Terraform in `terraform/` — Cloud Run service, Artifact Registry, service account, public IAM.

**Fully automated on merge to main** via `deploy.yml`:

1. Unit tests (pytest)
2. GCP auth via Workload Identity Federation (OIDC)
3. Database migrations (`alembic upgrade head`)
4. Docker build, tag with `github.sha` + `latest`, push to Artifact Registry
5. `terraform apply -auto-approve`
6. `gcloud run services update` with new image
7. Modal deploy (see above)

**Triggers:** Push to `main` touching `src/`, `docs/`, `terraform/`, `alembic/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, or the workflow file. Also supports manual `workflow_dispatch`.

**Terraform state:** GCS bucket with versioning.

**Gap:** Custom domain mapping (`v2.api.policyengine.org`) is manual via `gcloud` CLI.

## 4. policyengine.py Package

**Fully automated PyPI release** via `versioning.yaml`:

1. Contributors add changelog fragments to `changelog.d/` (e.g., `123.added.md`)
2. On merge to main, `bump_version.py` determines semver bump, updates `pyproject.toml`, commits
3. That commit triggers: build wheel + sdist → publish to PyPI → create git tag

**Testing:** Ruff lint + pytest on macOS (Python 3.13/3.14) on every PR and push to main.

## 5. App (policyengine-app-v2)

**Platform:** Vercel — auto-deploys on merge to main.

**CI/CD on every PR** (`pr.yaml`):

- Lint (Prettier + ESLint), TypeScript type checking, Vitest tests
- Embedded URL health checks, full build verification
- Chromatic visual regression testing

**Build:** Design system → LLMs.txt + sitemap → Vite website build → `app/dist`.

**Design system:** Auto-published to npm via `semantic-release` when `packages/design-system/**` changes.

**`move-to-api-v2` branch:** 138 commits rewriting the app for API v2 (new adapters, strategies, lazy metadata). Phase 5 migration complete. Switches Bun → npm. Ready to merge when API v2 is deployed.

## Summary

| Component | Deploy Trigger | Method | Automated? | Key Gap |
|-----------|---------------|--------|------------|---------|
| Supabase schema | Merge to main | `alembic upgrade head` in `deploy.yml` | Yes | — |
| Supabase RLS | Manual | `scripts/init.py` (defense-in-depth only) | No | API bypasses RLS via superuser |
| Supabase data | Manual workflow dispatch | `scripts/seed.py` | Partial | No scheduled re-seeding |
| Modal functions | Merge to main | `modal deploy` in `deploy.yml` | Yes | Uses git branch, not PyPI |
| Cloud Run API | Merge to main | Docker → Terraform → gcloud | Yes | Domain mapping is manual |
| policyengine.py | Merge to main + changelog fragment | Towncrier → PyPI | Yes | API uses git branch, not PyPI |
| App (Vercel) | Merge to main | Vercel auto-deploy | Yes | `move-to-api-v2` not merged yet |

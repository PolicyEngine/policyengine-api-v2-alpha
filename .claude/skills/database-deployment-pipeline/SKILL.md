---
name: Database Deployment Pipeline
description: >
  This skill should be used when the user asks about "database deployment",
  "how migrations run in production", "deploy.yml database step", "db-reset workflow",
  "why no create_all", "RLS policies deployment", "alembic in CI/CD",
  "lock_timeout", "seeding production", "init.py vs alembic",
  or needs to understand how schema changes reach the production Supabase database.
  Also relevant when modifying deploy.yml, db-reset.yml, alembic/env.py, or scripts/init.py.
version: 0.1.0
---

# Database Deployment Pipeline

This skill covers how database schema changes are deployed to the production Supabase (Postgres) database in the PolicyEngine API v2 project, and the design rationale behind the current architecture.

## Pipeline Overview

Two GitHub Actions workflows touch the production database. They serve different purposes and should never be confused:

| Workflow | Trigger | Effect | Destructive? |
|----------|---------|--------|--------------|
| `deploy.yml` | Merge to `main` (automatic) | Applies pending Alembic migrations | No |
| `db-reset.yml` | Manual dispatch only | Drops all tables, recreates, reseeds | Yes |

### deploy.yml — The Standard Path

On every merge to `main`, the deploy job runs `alembic upgrade head` against the production Supabase database **before** building the Docker image or updating Cloud Run. This ordering is critical: if the migration fails, the deploy stops and the old code continues running against the old schema.

The migration step uses `secrets.SUPABASE_DB_URL` (the direct connection on port 5432, not the pooler on port 6543) because DDL statements are incompatible with transaction-mode connection pooling.

The deploy is also triggered by changes to `alembic/**`, ensuring migration-only PRs trigger a deploy.

### db-reset.yml — The Nuclear Option

A manual-only workflow that drops the entire `public` schema, recreates it via Alembic, applies RLS policies, and reseeds data. Requires typing `reset-prod` to confirm and has a `production` environment approval gate.

Use this only when the database needs to be rebuilt from scratch (e.g., after a major schema redesign or data corruption). Never use it for routine schema changes.

## Key Design Decisions

### Migrations Run in CI/CD, Not at App Startup

The FastAPI app does **not** run migrations on startup. There is no `create_all()` or `alembic upgrade head` in the lifespan. This is intentional:

- Cloud Run may start multiple instances simultaneously. Concurrent DDL causes lock contention, race conditions, or duplicate migration attempts.
- Running migrations in CI/CD means they execute exactly once per deployment, from a single runner.
- If a migration fails, the deployment stops cleanly — no partially-migrated production state.

### RLS Policies Stay in scripts/init.py, Not Alembic

RLS policies are applied via `scripts/init.py` as idempotent raw SQL, not through Alembic migrations. This is intentional for this project's architecture:

- The API connects as the `postgres` superuser via SQLAlchemy, which **bypasses RLS entirely**. RLS only protects the Supabase PostgREST surface (anon/authenticated roles).
- Since RLS is defense-in-depth (not load-bearing), coupling it to schema migrations adds complexity with no runtime benefit.
- The idempotent `DROP POLICY IF EXISTS` + `CREATE POLICY` pattern in `init.py` can be re-run safely — a property that's useful for configuration but awkward in Alembic's run-once model.
- Alembic cannot autogenerate RLS changes, so every policy would be manual `op.execute()` SQL anyway.

If the project ever moves to an architecture where RLS is load-bearing (e.g., connecting as a non-superuser role), RLS policies should move into Alembic migrations alongside the table they protect. See `references/design-decisions.md` for the full rationale.

### lock_timeout Prevents Cascading Outages

`alembic/env.py` sets `lock_timeout=5000` (5 seconds) on the migration connection. Without this, a migration that can't acquire a lock waits indefinitely — and all new queries queue behind it, cascading into a full outage. With the timeout, the migration fails fast and the deploy stops cleanly.

## Common Operations

### Adding a new table

1. Create the SQLModel model in `src/policyengine_api/models/`
2. Export it in `models/__init__.py`
3. Generate migration: `uv run alembic revision --autogenerate -m "Add table_name table"`
4. **Read and verify** the generated migration file
5. Apply locally: `uv run alembic upgrade head`
6. If the table needs RLS protection on the PostgREST surface, add policies to `scripts/init.py`
7. Merge to `main` — migration runs automatically in `deploy.yml`

### Making a destructive schema change

Cloud Run uses rolling updates — old and new revisions serve traffic simultaneously. Destructive changes (drops, renames, type changes) require the expand-contract pattern across multiple deployments. See `references/design-decisions.md` for details.

### Full production database reset

1. Go to GitHub Actions > "Reset production database"
2. Select seeding mode (`lite` or `full`)
3. Type `reset-prod` in the confirmation field
4. Wait for the `production` environment approval
5. The workflow drops the schema, runs all migrations, applies RLS, and seeds data

## File Map

| File | Purpose |
|------|---------|
| `.github/workflows/deploy.yml` | Runs `alembic upgrade head` before Cloud Run update |
| `.github/workflows/db-reset.yml` | Manual destructive reset + reseed |
| `alembic/env.py` | Alembic config: reads `DATABASE_URL`, sets `NullPool` + `lock_timeout` |
| `alembic/versions/` | Migration files (source of truth for schema) |
| `scripts/init.py` | RLS policies, storage bucket setup, calls `alembic upgrade head` |
| `scripts/seed.py` | Populates models, variables, parameters, datasets |
| `src/policyengine_api/services/database.py` | SQLAlchemy engine + session factory (no `create_all`) |

## Additional Resources

### Reference Files

- **`references/design-decisions.md`** — Full rationale for RLS placement, connection types, zero-downtime migrations, and anti-patterns to avoid

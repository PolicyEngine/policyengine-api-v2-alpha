# Database Deployment Design Decisions

Detailed technical rationale behind the database deployment architecture. Consult this when modifying the pipeline or when the reasoning behind a decision is unclear.

## Why Migrations Run in CI/CD (Not at App Startup)

Four approaches were evaluated:

| Approach | Runs Once? | Blocks Deploy on Failure? | Safe for Multi-Instance? |
|----------|-----------|--------------------------|-------------------------|
| CI/CD step in deploy.yml | Yes | Yes | Yes |
| Cloud Run Job | Yes | Yes | Yes |
| FastAPI lifespan | No | No | No |
| Docker entrypoint | No | No | No |

**CI/CD step was chosen** because it's the simplest correct approach for a small team. Cloud Run Jobs would add Terraform complexity (a separate `google_cloud_run_v2_job` resource) for no practical benefit at current scale.

The lifespan and entrypoint approaches are dangerous because Cloud Run may start 2-10 instances simultaneously during a deployment. Each instance would attempt to run migrations concurrently, causing:
- Lock contention on DDL statements
- Race conditions where multiple instances try to create the same table
- Duplicate entries in `alembic_version`

The Alembic maintainer has confirmed that app-startup migrations are a fallback for environments that don't support arbitrary deploy commands — not the preferred approach.

## Why `create_all()` Was Removed

`SQLModel.metadata.create_all()` was previously called in the FastAPI lifespan via `init_db()`. This was removed because:

1. **It conflicts with Alembic.** `create_all()` creates tables that don't exist but does not modify existing tables (no column adds, type changes, renames, or drops). This means schema evolution silently fails — the app starts successfully but with a stale schema.
2. **It masks missing migrations.** If a developer forgets to generate a migration, `create_all()` might create the table anyway in some environments, hiding the problem until production.
3. **It has the same multi-instance problem.** Multiple Cloud Run instances calling `create_all()` simultaneously can cause conflicts.

With `create_all()` removed, a missing migration causes an immediate, visible failure — the app tries to query a table or column that doesn't exist, rather than silently operating against a partial schema.

## Why RLS Policies Are Not in Alembic

### The Core Insight: RLS Doesn't Protect This API

The API connects to Supabase as the `postgres` user. In Supabase, `postgres` has the `BYPASSRLS` privilege. Every query from the FastAPI app and Modal workers bypasses RLS entirely.

RLS policies only take effect when access goes through Supabase's PostgREST proxy — i.e., when using the Supabase client library with `anon` or `authenticated` JWT keys. The API uses the Supabase client **only for storage** (uploading/downloading HDF5 dataset files), not for table queries.

### Why init.py Is the Right Home

Given that RLS is defense-in-depth only:

1. **Idempotency is a feature, not a limitation.** The `DROP POLICY IF EXISTS` + `CREATE POLICY` pattern can be re-run safely. Alembic migrations run once and are tracked — re-running RLS setup is actually desirable for configuration.
2. **No tooling benefit from Alembic.** `alembic revision --autogenerate` cannot detect RLS changes. Every policy would be manual `op.execute()` raw SQL — identical to what `init.py` already does.
3. **Supabase's own tooling has RLS gaps.** `supabase db diff` cannot track `ALTER POLICY` statements. Even Supabase doesn't have a clean migration story for RLS.
4. **Simpler table creation.** Adding a new table doesn't require a separate migration file just for its RLS policy.

### When to Reconsider

Move RLS into Alembic if the architecture changes such that:
- The API connects as a non-superuser role (not `postgres`)
- RLS becomes the primary access control mechanism (not just defense-in-depth)
- Tables need different policies at different points in time (versioned evolution)

In that case, include RLS policies in the same Alembic migration that creates the table:

```python
def upgrade():
    op.create_table("some_table", ...)
    op.execute("ALTER TABLE some_table ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY "Service role full access" ON some_table
        FOR ALL TO service_role USING (true) WITH CHECK (true)
    """)

def downgrade():
    op.execute('DROP POLICY IF EXISTS "Service role full access" ON some_table')
    op.drop_table("some_table")
```

## Connection Types for Supabase

Supabase exposes two connection endpoints. Use the correct one for each operation:

| Operation | Connection | Port | Why |
|-----------|-----------|------|-----|
| Alembic migrations | Direct (`db.project.supabase.co`) | 5432 | DDL needs full Postgres features |
| FastAPI application | Pooler (`pooler.supabase.com`) | 6543 | Efficient connection reuse |
| `scripts/init.py` | Pooler | 6543 | Mostly DML (RLS policies are DDL but lightweight) |

The direct connection uses IPv6 by default. GitHub Actions runners support IPv6, so this works for CI/CD.

`alembic/env.py` uses `NullPool` because Supabase manages connection pooling on its side. Creating a client-side pool on top of server-side pooling wastes connections.

## Zero-Downtime Migration Pattern

Cloud Run uses rolling updates: during deployment, both old and new revisions serve traffic simultaneously. Schema changes must be backwards-compatible with the old code.

### Additive Changes (Safe in One Deploy)

- Adding a new column (nullable or with a default)
- Adding a new table
- Adding an index

These are safe because old code simply ignores the new column/table.

### Destructive Changes (Require Expand-Contract)

Dropping columns, renaming columns, or changing column types require three separate deployments:

**Deploy 1 — Expand:** Add the new column/table. Old code ignores it.

```python
def upgrade():
    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))
```

**Deploy 2 — Migrate:** New code writes to both old and new columns. Run a backfill for existing data.

**Deploy 3 — Contract:** Drop the old column after all instances use the new code.

```python
def upgrade():
    op.drop_column("users", "first_name")
    op.drop_column("users", "last_name")
```

### Index Creation on Large Tables

Standard `CREATE INDEX` acquires an exclusive lock, blocking all reads and writes. For large tables, use `CREATE INDEX CONCURRENTLY`:

```python
def upgrade():
    op.execute("CREATE INDEX CONCURRENTLY idx_users_email ON users (email)")
```

Note: `CONCURRENTLY` cannot run inside a transaction. Use `op.get_context().autocommit_block()` or set the migration to non-transactional.

## Anti-Patterns to Avoid

### Editing Applied Migration Files

Never modify a migration that has already been applied to production. Alembic tracks migrations by revision ID — editing a file does not re-run it. Create a new migration to fix issues.

### Mixing Schema and Data Migrations

A single migration that both alters the schema and backfills millions of rows holds locks for extended periods. Schema changes should be deploy-time migrations. Data backfills should be separate scripts or background jobs.

### Running Migrations Without lock_timeout

Without `lock_timeout`, a migration waits indefinitely for a lock on a table with long-running queries. All new queries queue behind the migration's lock request, cascading into a full outage. The 5-second timeout in `alembic/env.py` ensures the migration fails fast instead.

### Using the Pooler for Migrations

Transaction-mode pooling (port 6543) is incompatible with DDL statements and prepared statements. Always use the direct connection (port 5432) for Alembic operations. The `deploy.yml` workflow uses `secrets.SUPABASE_DB_URL` (direct), while `db-reset.yml` uses `secrets.SUPABASE_POOLER_URL` — note this difference if modifying the workflows.

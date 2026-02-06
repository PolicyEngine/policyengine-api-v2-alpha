# Supabase & Database Migration Notes

## Overview

This document summarizes the database setup, migration issues, and workarounds discovered during local development of the PolicyEngine API v2.

---

## What is Supabase?

Supabase is a backend-as-a-service platform that provides:
- **PostgreSQL database** - The actual database
- **PostgREST** - Auto-generated REST API from your database schema
- **GoTrue** - Authentication service
- **Kong** - API gateway
- **Studio** - Web UI for managing your database
- **Realtime** - WebSocket subscriptions for live updates
- **Storage** - File storage with CDN

### Local Development with Supabase

Running `supabase start` spins up Docker containers for all these services locally:
- PostgreSQL on port **54322**
- Studio UI on port **54323**
- API on port **54321**

---

## The Migration Bug

### What Happened

When running `supabase start` on a fresh machine, it failed with:

```
ERROR: relation "parameter_values" does not exist (SQLSTATE 42P01)
```

### Root Cause

The migration file `20251229000000_add_parameter_values_indexes.sql` tries to create an index on the `parameter_values` table:

```sql
CREATE INDEX idx_parameter_values_parameter_id ON parameter_values(parameter_id);
```

But there's **no base schema migration** that creates the tables first. The migrations run in timestamp order, so this index migration runs before any tables exist.

### Why This Wasn't Caught Before

Different developers may have had working setups because:

1. **SQLite for local dev** - Using `SUPABASE_DB_URL="sqlite:///./test.db"` bypasses Supabase entirely. SQLModel's `create_all()` auto-creates tables.

2. **Existing PostgreSQL** - If someone had previously created tables manually or through the API startup, the migration would succeed.

3. **Never ran `supabase start`** - The migrations only run when Supabase starts fresh.

---

## Two Ways Tables Get Created

### 1. SQLModel's `create_all()` (Automatic)

When the API starts, this code runs in `database.py`:

```python
def init_db():
    SQLModel.metadata.create_all(engine)
```

This automatically creates all tables defined in SQLModel classes. It's idempotent (safe to run multiple times) but:
- Doesn't track schema changes over time
- Can't roll back changes
- Doesn't work for Supabase migrations (they run BEFORE the API starts)

### 2. Migration Scripts (Manual/Versioned)

SQL files in `supabase/migrations/` that run in timestamp order:
- `20241119000000_storage_bucket.sql`
- `20241121000000_storage_policies.sql`
- `20251229000000_add_parameter_values_indexes.sql` ← Problem file
- `20260103000000_add_poverty_inequality.sql`
- `20260111000000_add_aggregate_status.sql`

**Why migrations exist:**
- Version-controlled schema changes
- Can roll back to previous versions
- Team members get same schema automatically
- Production deployments are reproducible

---

## The Fix (Not Yet Implemented)

Add a base schema migration with an earlier timestamp that creates all tables:

```
supabase/migrations/20241101000000_base_schema.sql
```

This file should contain `CREATE TABLE` statements for all tables, generated from the SQLModel definitions.

---

## Workaround: Use SQLite for Local Testing

For quick local development without Docker/Supabase:

```bash
cd /Users/sakshikekre/Work/PolicyEngine/Repos/policyengine-api-v2-alpha

# Start API with SQLite instead of PostgreSQL
SUPABASE_DB_URL="sqlite:///./test.db" .venv/bin/uvicorn policyengine_api.main:app --host 0.0.0.0 --port 8000 --reload
```

This:
- Creates a local `test.db` file
- SQLModel auto-creates all tables on startup
- No Docker required
- Fast iteration for development

---

## Docker/Colima Setup (For Full Supabase)

Supabase local requires Docker. Options:

### Option A: Docker Desktop (~2-3GB)
```bash
brew install --cask docker
# Then open Docker Desktop app
```

### Option B: Colima (Lightweight, ~500MB)
```bash
brew install colima docker docker-compose
colima start
```

**Note:** Colima installation failed due to disk space. Need ~2GB free for the build process.

---

## Current .env Configuration

```env
# For Supabase (when running)
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# For SQLite (workaround)
SUPABASE_DB_URL=sqlite:///./test.db
```

---

## Summary

| Approach | Pros | Cons |
|----------|------|------|
| **SQLite** | Fast, no Docker, instant tables | Not production-like, some SQL differences |
| **Supabase** | Production-like, full stack | Needs Docker, migration bug to fix |

**Recommended for now:** Use SQLite for development until the base schema migration is added.

---

## TODO

- [ ] Create `20241101000000_base_schema.sql` with all table definitions
- [ ] Test `supabase start` with the new migration
- [ ] Free up disk space and install Colima/Docker
- [ ] Document the full Supabase setup process

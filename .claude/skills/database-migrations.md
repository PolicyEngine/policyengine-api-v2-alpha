# Database Migration Guidelines

## Overview

This project uses **Alembic** for database migrations with **SQLModel** models. Alembic is the industry-standard migration tool for SQLAlchemy/SQLModel projects.

**CRITICAL**: SQL migrations are the single source of truth for database schema. All table creation and schema changes MUST go through Alembic migrations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SQLModel Models (src/policyengine_api/models/)             │
│  - Define Python classes                                     │
│  - Used for ORM queries                                      │
│  - NOT the source of truth for schema                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ alembic revision --autogenerate
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Alembic Migrations (alembic/versions/)                     │
│  - Create/alter tables                                       │
│  - Add indexes, constraints                                  │
│  - SOURCE OF TRUTH for schema                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ alembic upgrade head
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL Database (Supabase)                             │
│  - Actual schema                                             │
│  - Tracked by alembic_version table                         │
└─────────────────────────────────────────────────────────────┘
```

## Essential Rules

### 1. NEVER use SQLModel.metadata.create_all() for schema creation

The old pattern of using `SQLModel.metadata.create_all()` is deprecated. All tables are created via Alembic migrations.

### 2. Every schema change requires a migration

When you modify a SQLModel model (add column, change type, add index), you MUST:
1. Update the model in `src/policyengine_api/models/`
2. Generate a migration: `uv run alembic revision --autogenerate -m "Description"`
3. **Read and verify the generated migration** (see below)
4. Apply it: `uv run alembic upgrade head`

### 3. ALWAYS verify auto-generated migrations before applying

**This is critical for AI agents.** After running `alembic revision --autogenerate`, you MUST:

1. **Read the generated migration file** in `alembic/versions/`
2. **Verify the `upgrade()` function** contains the expected changes:
   - Correct table/column names
   - Correct column types (e.g., `sa.String()`, `sa.Uuid()`, `sa.Integer()`)
   - Proper foreign key references
   - Appropriate nullable settings
3. **Verify the `downgrade()` function** properly reverses the changes
4. **Check for Alembic autogenerate limitations:**
   - It may miss renamed columns (shows as drop + add instead)
   - It may not detect some index changes
   - It doesn't handle data migrations
5. **Edit the migration if needed** before applying

Example verification:
```python
# Generated migration - verify this looks correct:
def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'phone')
```

**Never blindly apply a migration without reading it first.**

### 4. Migrations must be self-contained

Each migration should:
- Create tables it needs (never assume they exist from Python)
- Include both `upgrade()` and `downgrade()` functions
- Be idempotent where possible (use `IF NOT EXISTS` patterns)

### 5. Never use conditional logic based on table existence

Migrations should NOT check if tables exist. Instead:
- Ensure migrations run in the correct order (use `down_revision`)
- The initial migration creates all base tables
- Subsequent migrations build on that foundation

## Common Commands

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Generate migration from model changes
uv run alembic revision --autogenerate -m "Add users email index"

# Create empty migration (for manual SQL)
uv run alembic revision -m "Add custom index"

# Check current migration state
uv run alembic current

# Show migration history
uv run alembic history

# Downgrade one revision
uv run alembic downgrade -1

# Downgrade to specific revision
uv run alembic downgrade <revision_id>
```

## Local Development Workflow

```bash
# 1. Start Supabase
supabase start

# 2. Initialize database (runs migrations + applies RLS policies)
uv run python scripts/init.py

# 3. Seed data
uv run python scripts/seed.py
```

### Reset database (DESTRUCTIVE)

```bash
uv run python scripts/init.py --reset
```

## Adding a New Model

1. Create the model in `src/policyengine_api/models/`

```python
# src/policyengine_api/models/my_model.py
from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4

class MyModel(SQLModel, table=True):
    __tablename__ = "my_models"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
```

2. Export in `__init__.py`:

```python
# src/policyengine_api/models/__init__.py
from .my_model import MyModel
```

3. Generate migration:

```bash
uv run alembic revision --autogenerate -m "Add my_models table"
```

4. Review the generated migration in `alembic/versions/`

5. Apply the migration:

```bash
uv run alembic upgrade head
```

6. Update `scripts/init.py` to include the table in RLS policies if needed.

## Adding an Index

1. Generate a migration:

```bash
uv run alembic revision -m "Add index on users.email"
```

2. Edit the migration:

```python
def upgrade() -> None:
    op.create_index("idx_users_email", "users", ["email"])

def downgrade() -> None:
    op.drop_index("idx_users_email", "users")
```

3. Apply:

```bash
uv run alembic upgrade head
```

## Production Considerations

### Applying migrations to production

1. Migrations are automatically applied when deploying
2. Always test migrations locally first
3. For data migrations, consider running during low-traffic periods

### Transitioning production from old system to Alembic

Production databases that were created before Alembic (using the old `SQLModel.metadata.create_all()` approach or raw Supabase migrations) need special handling. Running `alembic upgrade head` would fail because the tables already exist.

**The solution: `alembic stamp`**

The `alembic stamp` command marks a migration as "already applied" without actually running it. This tells Alembic "the database is already at this state, start tracking from here."

**How it works:**

1. `alembic stamp <revision_id>` inserts a row into the `alembic_version` table with the specified revision ID
2. Alembic now thinks that migration (and all migrations before it) have been applied
3. Future migrations will run normally starting from that point

**Step-by-step production transition:**

```bash
# 1. Connect to production database
# (set SUPABASE_DB_URL or other connection env vars)

# 2. Check if alembic_version table exists
# If not, Alembic will create it automatically

# 3. Verify production schema matches the initial migration
# Compare tables/columns in production against alembic/versions/20260204_d6e30d3b834d_initial_schema.py

# 4. Stamp the initial migration as applied
uv run alembic stamp d6e30d3b834d

# 5. If production also has the indexes from the second migration, stamp that too
uv run alembic stamp a17ac554f4aa

# 6. Verify the stamp worked
uv run alembic current
# Should show: a17ac554f4aa (head)

# 7. From now on, new migrations will apply normally
uv run alembic upgrade head
```

**Handling partially applied migrations:**

If production has some but not all changes from a migration:

1. Manually apply the missing changes via SQL
2. Then stamp that migration as complete
3. Or: create a new migration that only adds the missing pieces

**After stamping:**

- All future schema changes go through Alembic migrations
- Developers generate migrations with `alembic revision --autogenerate`
- Deployments run `alembic upgrade head` to apply pending migrations
- The `alembic_version` table tracks what's been applied

## File Structure

```
alembic/
├── env.py              # Alembic configuration (imports models, sets DB URL)
├── script.py.mako      # Template for new migrations
├── versions/           # Migration files
│   ├── 20260204_d6e30d3b834d_initial_schema.py
│   └── 20260204_a17ac554f4aa_add_parameter_values_indexes.py
alembic.ini             # Alembic settings

supabase/
├── migrations/         # Supabase-specific migrations (storage only)
│   ├── 20241119000000_storage_bucket.sql
│   └── 20241121000000_storage_policies.sql
└── migrations_archived/  # Old table migrations (now in Alembic)
```

## Troubleshooting

### "Target database is not up to date"

Run `alembic upgrade head` to apply pending migrations.

### "Can't locate revision"

The alembic_version table has a revision that doesn't exist in your migrations folder. This can happen if someone deleted a migration file. Fix by stamping to a known revision:

```bash
alembic stamp head  # If tables are current
alembic stamp d6e30d3b834d  # If at initial schema
```

### "Table already exists"

The migration is trying to create a table that already exists. Options:
1. If this is a fresh setup, drop and recreate: `uv run python scripts/init.py --reset`
2. If in production, stamp the migration as applied: `alembic stamp <revision>`

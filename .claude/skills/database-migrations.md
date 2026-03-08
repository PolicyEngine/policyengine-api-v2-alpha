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

### 1. NEVER use SQLModel.metadata.create_all()

`create_all()` is not used anywhere in this project. It was removed because it conflicts with Alembic (creates tables but can't modify them, masking missing migrations). For how migrations reach production, see the `database-deployment-pipeline` skill.

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

Migrations are automatically applied in `deploy.yml` (runs `alembic upgrade head` before updating Cloud Run). For full details on the production pipeline, connection types, lock_timeout, RLS policy handling, and zero-downtime patterns, see the `database-deployment-pipeline` skill.

### alembic stamp (for one-time transitions)

If production has tables that predate Alembic, use `alembic stamp <revision_id>` to mark migrations as already applied without running them. This tells Alembic to start tracking from that point forward.

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

# Supabase setup

This guide covers setting up Supabase for PolicyEngine API development.

## Local development

### Install Supabase CLI

```bash
# macOS
brew install supabase/tap/supabase

# Linux/WSL
curl -sSfL https://supabase.com/install.sh | sh

# Windows (PowerShell)
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase
```

### Initialize Supabase

```bash
# Initialize in project directory
cd policyengine-api-v2
supabase init
```

### Start Supabase

```bash
supabase start
```

This starts:
- PostgreSQL database on port 54322
- Studio dashboard on port 54323
- API server on port 54321
- Storage API
- Auth API

### Get connection details

```bash
supabase status
```

Copy the values to `.env`:

```bash
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=<anon key from supabase status>
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres
```

### Apply migrations

Migrations are applied automatically when you run `supabase start`. To create new migrations:

```bash
supabase migration new migration_name
```

### Stop Supabase

```bash
supabase stop
```

### Reset database

```bash
supabase db reset
```

## Production deployment

### Create Supabase project

1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Note down the URL and anon key

### Link local to remote

```bash
supabase link --project-ref your-project-ref
```

### Push migrations

```bash
supabase db push
```

### Update environment variables

Set production environment variables:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.your-project.supabase.co:5432/postgres
```

## Storage setup

The datasets bucket is created automatically by the migration. To verify:

```bash
# Via CLI
supabase storage list

# Via Studio
# Navigate to http://localhost:54323 → Storage
```

### Upload datasets

```python
from policyengine_api.services import storage

# Upload local file
url = storage.upload_dataset("./data/frs_2023_24.h5", "frs_2023_24.h5")
print(f"Uploaded to: {url}")

# List files
files = storage.list_datasets()
for f in files:
    print(f"{f['name']}: {f['size']} bytes")
```

## Database schema

Schema is managed via Alembic migrations. The SQLModel models automatically generate the schema:

```bash
# Create migration
alembic revision --autogenerate -m "add new table"

# Apply migrations
alembic upgrade head
```

## Useful commands

```bash
# View logs
supabase logs

# Open Studio
supabase studio

# Dump database
supabase db dump -f dump.sql

# Restore database
psql postgresql://postgres:postgres@localhost:54322/postgres < dump.sql
```

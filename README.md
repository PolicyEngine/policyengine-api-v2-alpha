# PolicyEngine API v2

A FastAPI service for running PolicyEngine microsimulations with Supabase backend, object storage, and background task processing.

## Features

- RESTful API for creating and managing simulations
- Supabase for database and storage
- Redis caching and Celery for background task processing
- SQLModel for type-safe database models
- Terraform deployment to AWS

## Quick start

### Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Docker and Docker Compose
- Python 3.11+

### Local development with Supabase

1. **Set up environment**

Copy the example environment file:

```bash
cp .env.example .env
```

The `.env` file contains default values for local Supabase development. Key variables:

```bash
# Supabase local instance (defaults work with `supabase start`)
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_KEY=<anon-key>                  # Public anon key
SUPABASE_SERVICE_KEY=<service-role-key>  # Admin key for seeding
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# Storage
STORAGE_BUCKET=datasets

# Redis (via Docker)
REDIS_URL=redis://localhost:6379/0
```

**Important:** The service key is required for database seeding operations (uploading datasets to storage). The default keys in `.env.example` work with local Supabase.

2. **Start Supabase**

```bash
supabase start
```

This creates a local instance at `http://localhost:54321` with:
- PostgreSQL on port 54322
- Storage API with S3-compatible interface
- Auth API
- Studio dashboard at `http://localhost:54323`

3. **Run integration tests**

This will set up the database, seed it with UK/US models, and run tests:

```bash
make integration-test
```

This command:
- Starts Supabase (if not running)
- Creates all database tables from SQLModel definitions
- Applies RLS policies and storage bucket configuration
- Seeds UK and US tax-benefit models with all variables, parameters, and datasets
- Runs integration tests to verify everything works

4. **Start the API**

```bash
docker compose up
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

## Observability

The API uses [Logfire](https://logfire.pydantic.dev/) for observability and monitoring. Logfire automatically instruments:
- All HTTP requests and responses
- Database queries
- Background tasks
- Performance metrics

To view traces and logs, visit the [Logfire dashboard](https://logfire.pydantic.dev).

## Architecture

The system consists of three main components:

1. **API server** - FastAPI application serving REST endpoints
2. **Database** - Supabase PostgreSQL storing models, parameters, simulations
3. **Storage** - Supabase storage for dataset files (.h5)
4. **Worker** - Celery workers executing simulations in background

### Models

The API provides eleven core resources:

- **Datasets** - Microdata for simulations (stored in Supabase storage)
- **Policies** - Parametric reforms to tax-benefit systems
- **Simulations** - Execution of tax-benefit models on datasets
- **Variables** - Calculated outputs (income_tax, universal_credit, etc.)
- **Parameters** - System settings (personal_allowance, benefit_rates, etc.)
- **ParameterValues** - Time-bound parameter values
- **Dynamics** - Dynamic modeling configurations
- **TaxBenefitModels** - Country models (UK, US)
- **TaxBenefitModelVersions** - Model versions
- **AggregateOutputs** - Aggregate statistics from simulations
- **ChangeAggregates** - Reform impact analysis

### Workflow

1. Upload dataset: `POST /datasets` with file upload to Supabase storage
2. Create policy reform: `POST /policies`
3. Create simulation: `POST /simulations`
4. Poll simulation status: `GET /simulations/{id}`
5. Create aggregates: `POST /outputs/aggregate`

## API endpoints

All endpoints at root level:

```bash
GET  /health                           → {"status": "healthy"}
GET  /datasets                         → List all datasets
POST /datasets                         → Create dataset
GET  /policies                         → List all policies
POST /policies                         → Create policy
GET  /simulations                      → List all simulations
POST /simulations                      → Create and queue simulation
GET  /variables                        → List all variables
GET  /parameters                       → List all parameters
GET  /parameter-values                 → List all parameter values
GET  /dynamics                         → List all dynamics
GET  /tax-benefit-models               → List all models
GET  /tax-benefit-model-versions       → List all model versions
GET  /outputs/aggregate                → List aggregates
POST /outputs/aggregate                → Compute aggregate
GET  /change-aggregates                → List change aggregates
POST /change-aggregates                → Compute reform impact

POST /initialize/uk                    → Initialize UK model
POST /initialize/us                    → Initialize US model
```

## Configuration

Set environment variables or create a `.env` file:

```bash
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=your-anon-key
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
STORAGE_BUCKET=datasets
DEBUG=false
```

## Storage

Datasets are stored in Supabase storage:

```python
from policyengine_api.services import storage

# Upload dataset
url = storage.upload_dataset("/path/to/dataset.h5", "frs_2023_24.h5")

# Download dataset
storage.download_dataset("frs_2023_24.h5", "/local/path.h5")

# Get public URL
url = storage.get_dataset_url("frs_2023_24.h5")

# List all datasets
files = storage.list_datasets()
```

## Development

### Running tests

```bash
pytest
```

### Code formatting

```bash
ruff format .
ruff check --fix .
```

### Database schema

The database schema uses a hybrid approach:

**SQLModel for tables:** All table schemas are defined in Python using SQLModel (see `src/policyengine_api/models/`). This provides:
- Single source of truth in Python code
- Type safety and IDE autocomplete
- Automatic relationship handling
- Easy testing

**SQL migrations for Postgres features:** SQL files in `supabase/migrations/` handle:
- Row-level security (RLS) policies
- Storage bucket configuration
- Postgres-specific features SQLModel can't express

To regenerate the schema:

```bash
# Creates all tables from SQLModel and applies SQL migrations
uv run python scripts/create_tables.py
```

**When to create SQL migrations:**

Only create new SQL migrations for RLS policies, storage buckets, or other Postgres-specific features. Table schemas should be defined in SQLModel classes, not SQL.

```bash
# Create a new migration (only for RLS/storage/triggers)
supabase migration new add_new_rls_policy
```

### Supabase management

```bash
# Start local Supabase
supabase start

# Stop Supabase
supabase stop

# Reset database
supabase db reset

# View logs
supabase logs

# Open Studio dashboard
supabase studio
```

## Project structure

```
policyengine-api-v2/
├── src/
│   └── policyengine_api/
│       ├── api/              # FastAPI routers
│       ├── config/           # Settings
│       ├── models/           # SQLModel database models
│       ├── services/         # Database, storage, initialization
│       ├── tasks/            # Celery tasks
│       └── main.py           # FastAPI application
├── supabase/                 # Supabase configuration and migrations
├── tests/                    # Test suite
├── docker-compose.yml        # Docker services (API, worker, Redis)
└── pyproject.toml            # Dependencies
```

## License

AGPL-3.0

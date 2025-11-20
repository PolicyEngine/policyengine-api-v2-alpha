# PolicyEngine API v2

A FastAPI service for running PolicyEngine microsimulations with Supabase backend, object storage, and background task processing.

## Features

- RESTful API for creating and managing simulations
- Supabase for database and storage
- Redis + Celery for background task processing
- SQLModel for type-safe database models
- Terraform deployment to AWS

## Quick start

### Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Docker and Docker Compose
- Python 3.11+

### Local development with Supabase

1. Start Supabase locally:

```bash
supabase start
```

This creates a local Supabase instance at `http://localhost:54321` with:
- PostgreSQL database on port 54322
- Storage API
- Auth API
- Studio dashboard at `http://localhost:54323`

2. Copy environment variables:

```bash
cp .env.example .env
```

Update `.env` with your Supabase credentials from `supabase status`:

```bash
supabase status
```

3. Seed the database with UK and US tax-benefit models:

```bash
make seed
```

This will:
- Load all variables and parameters from policyengine-uk and policyengine-us
- Populate the database with all models, versions, parameters, and variables

4. Start Redis and the API:

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
5. Create aggregate outputs: `POST /outputs/aggregate`

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
GET  /outputs/aggregate                → List aggregate outputs
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

### Database migrations

Create a new migration:

```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:

```bash
alembic upgrade head
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
├── supabase/                 # Supabase configuration
├── migrations/               # Alembic migrations
├── tests/                    # Test suite
├── docker-compose.yml        # Docker services (API, worker, Redis)
└── pyproject.toml            # Dependencies
```

## License

AGPL-3.0

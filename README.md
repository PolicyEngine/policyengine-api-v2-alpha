# PolicyEngine API v2

FastAPI service for PolicyEngine microsimulations with Supabase backend and object storage.

## Features

- RESTful API for tax-benefit microsimulations
- Supabase for PostgreSQL database and object storage
- Modal.com serverless compute with sub-1s cold starts
- SQLModel for type-safe database models
- Logfire observability and monitoring
- Terraform deployment to GCP Cloud Run

## Quick start

### Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Docker and Docker Compose
- Python 3.13+ with uv

### Local development

1. **Set up environment**

```bash
cp .env.example .env
```

The defaults in `.env.example` work with local Supabase. Key settings:

```bash
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
STORAGE_BUCKET=datasets
```

2. **Start Supabase**

```bash
supabase start
```

Creates a local instance with PostgreSQL (port 54322), Storage API, and Studio dashboard at `http://localhost:54323`.

3. **Initialise database**

```bash
make init
```

This resets the database, creates tables, storage bucket, and RLS policies.

4. **Seed data**

```bash
make seed
```

Seeds UK and US tax-benefit models with variables, parameters, and datasets.

5. **Start the API**

```bash
docker compose up
```

API available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive documentation.

## API endpoints

Base URL: `http://localhost:8000`

### Core resources

```
GET  /health                           → Health check
GET  /datasets                         → List datasets
POST /datasets                         → Create dataset
GET  /policies                         → List policies
POST /policies                         → Create policy
GET  /dynamics                         → List dynamics
POST /dynamics                         → Create dynamic
GET  /simulations                      → List simulations
POST /simulations                      → Create simulation
GET  /simulations/{id}                 → Get simulation status
```

### Model metadata

```
GET  /variables                        → List variables
GET  /parameters                       → List parameters
GET  /parameter-values                 → List parameter values
GET  /tax-benefit-models               → List models
GET  /tax-benefit-model-versions       → List model versions
```

### Aggregates and analysis

```
GET  /aggregates                       → List aggregates
POST /aggregates                       → Create aggregate
GET  /aggregates/{id}                  → Get aggregate
GET  /change-aggregates                → List change aggregates
POST /change-aggregates                → Create change aggregate
GET  /change-aggregates/{id}           → Get change aggregate
DELETE /change-aggregates/{id}         → Delete change aggregate
```

## Typical workflow

1. Create simulation: `POST /simulations` with dataset and policy
2. Poll status: `GET /simulations/{id}` until status is "completed"
3. Request aggregates: `POST /aggregates` with simulation_id and variable
4. Compare reforms: `POST /change-aggregates` with baseline and reform simulation IDs

## Database management

### Local development

```bash
make init             # Reset and initialise Supabase (tables, buckets, permissions)
make seed             # Seed UK/US models only
make integration-test # Full setup: init, seeding, tests
make reset            # Reset Supabase database (supabase db reset)
```

### Production

```bash
make db-reset-prod    # Reset production database (requires confirmation)
```

**Warning:** `db-reset-prod` drops all tables and storage, recreates everything, and reseeds data. Requires typing "yes" to confirm.

## Development

### Code quality

```bash
make format          # Format code with ruff
make lint            # Lint and fix with ruff
make test            # Run unit tests
```

### Database schema

Schema is defined in two parts:

**SQLModel tables** (`src/policyengine_api/models/`): All table definitions use SQLModel for type safety and single source of truth.

**SQL migrations** (`supabase/migrations/`): Row-level security policies, storage buckets, and Postgres-specific features.

To reset and recreate everything:

```bash
uv run python scripts/init.py
```

This drops all tables, deletes the storage bucket, then recreates tables from SQLModel and applies RLS policies.

## Observability

[Logfire](https://logfire.pydantic.dev/) instruments HTTP requests, database queries, and performance metrics. View traces at the [Logfire dashboard](https://logfire.pydantic.dev).

## Architecture

### Components

- **API server**: FastAPI application (port 8000)
- **Database**: Supabase PostgreSQL
- **Storage**: Supabase object storage for .h5 dataset files
- **Compute**: Modal.com serverless functions for simulations

### Data models

- **Datasets**: Microdata files in Supabase storage
- **DatasetVersions**: Versioned dataset snapshots
- **Policies**: Parameter reforms
- **Dynamics**: Dynamic behavioural responses
- **Simulations**: Tax-benefit calculations
- **Variables**: Model outputs (income_tax, universal_credit)
- **Parameters**: System settings (personal_allowance, benefit_rates)
- **ParameterValues**: Time-bound parameter values
- **Aggregates**: Statistics from simulations
- **ChangeAggregates**: Reform impact analysis

### Project structure

```
policyengine-api-v2/
├── src/policyengine_api/
│   ├── api/              # FastAPI routers
│   ├── config/           # Settings
│   ├── models/           # SQLModel database models
│   ├── services/         # Database, storage
│   ├── modal_app.py      # Modal.com serverless functions
│   └── main.py           # FastAPI app
├── supabase/
│   └── migrations/       # RLS policies and storage
├── scripts/              # Database init and seeding
├── terraform/            # GCP Cloud Run deployment
├── tests/                # Test suite
└── docker-compose.yml    # Local services
```

## License

AGPL-3.0

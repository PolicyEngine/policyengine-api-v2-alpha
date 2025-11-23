# PolicyEngine API v2

FastAPI service for PolicyEngine microsimulations with Supabase backend, object storage, and background task processing.

## Features

- RESTful API for tax-benefit microsimulations
- Supabase for PostgreSQL database and object storage
- Celery workers for background simulation tasks
- SQLModel for type-safe database models
- Logfire observability and monitoring
- Terraform deployment to AWS

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
REDIS_URL=redis://localhost:6379/0
STORAGE_BUCKET=datasets
```

2. **Start Supabase**

```bash
supabase start
```

Creates a local instance with PostgreSQL (port 54322), Storage API, and Studio dashboard at `http://localhost:54323`.

3. **Run integration tests**

Sets up database, seeds models, and runs tests:

```bash
make integration-test
```

This command:
- Creates all database tables from SQLModel definitions
- Applies RLS policies and storage bucket migrations
- Seeds UK and US tax-benefit models with variables, parameters, and datasets
- Runs integration tests

4. **Start the API**

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
make integration-test  # Full setup: tables, migrations, seeding, tests
make seed             # Seed UK/US models only
make reset            # Reset Supabase database
```

### Production

```bash
make db-reset-prod    # Reset production database (requires confirmation)
```

**Warning:** `db-reset-prod` drops all tables, recreates schema, and reseeds data. It requires typing "yes" to confirm.

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

To recreate tables:

```bash
uv run python scripts/create_tables.py
```

Only create SQL migrations for RLS policies or storage configuration, not table schemas.

## Observability

[Logfire](https://logfire.pydantic.dev/) instruments:
- HTTP requests and responses
- Database queries
- Background tasks
- Performance metrics

View traces at the [Logfire dashboard](https://logfire.pydantic.dev).

## Architecture

### Components

- **API server**: FastAPI application (port 8000 local, 80 production)
- **Database**: Supabase PostgreSQL
- **Storage**: Supabase object storage for .h5 dataset files
- **Worker**: Celery workers for background simulations
- **Cache**: Redis for Celery broker and API caching

### Data models

- **Datasets**: Microdata files in Supabase storage
- **Policies**: Parameter reforms
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
│   ├── tasks/            # Celery tasks
│   └── main.py           # FastAPI app
├── supabase/
│   └── migrations/       # RLS policies and storage
├── scripts/              # Database setup and seeding
├── tests/                # Test suite
└── docker-compose.yml    # Local services
```

## License

AGPL-3.0

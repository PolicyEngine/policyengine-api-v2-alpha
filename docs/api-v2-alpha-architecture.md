# policyengine-api-v2-alpha Deep Dive

## Overview

A **FastAPI backend** for tax-benefit policy microsimulations using PolicyEngine's UK and US models. It's designed as a thin orchestration layer that offloads heavy calculations to **Modal.com** serverless functions.

---

## Architecture

### Three-Level Hierarchy
```
Level 2: Reports        AI-generated analysis documents
Level 1: Analyses       Comparisons (economy_comparison_*)
Level 0: Simulations    Single calculations (simulate_household_*, simulate_economy_*)
```

### Request Flow
1. Client → FastAPI (Cloud Run)
2. API creates job record in **Supabase** and triggers **Modal.com** function
3. Modal runs calculation with pre-loaded PolicyEngine models (sub-1s cold start via memory snapshotting)
4. Modal writes results directly to Supabase
5. Client polls API until `status = "completed"`

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI + async |
| Database | Supabase (PostgreSQL) via SQLModel |
| Compute | Modal.com serverless |
| Storage | Supabase Storage (S3-compatible for .h5 datasets) |
| Package mgr | UV |
| Formatting | Ruff |
| Testing | Pytest + pytest-asyncio |
| Deployment | Terraform → GCP Cloud Run |
| Observability | Logfire (OpenTelemetry) |

---

## Database Models (SQLModel)

### Core Entities

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `TaxBenefitModel` | Country identifier | `name` ("uk"/"us") |
| `TaxBenefitModelVersion` | Version of model | `version`, FK to model |
| `Dataset` | Population microdata (.h5) | `filepath` (S3), `year` |
| `DatasetVersion` | Dataset versions | FK to dataset + model |
| `User` | Basic user info | `email`, `first_name`, `last_name` |

### Policy System (Normalized)

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Policy` | Policy reform definition | `name`, `description`, `simulation_modifier` (Python code) |
| `Parameter` | Tax/benefit parameter metadata | `name` (path), `label`, `data_type`, FK to model version |
| `ParameterValue` | Parameter values (baseline OR reform) | `value_json`, `start_date`, `policy_id` (NULL=baseline) |
| `Variable` | Model variables metadata | `name`, `entity`, `data_type`, `possible_values` |
| `Dynamic` | Behavioral response config | Similar to Policy |

### Simulation & Results

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Simulation` | Economy simulation instance | FK to dataset, policy, dynamic; `status` |
| `HouseholdJob` | Single household calculation | `request_data` (JSON), `result` (JSON), `status` |
| `Report` | Analysis report | FK to baseline_sim, reform_sim; `status`, `markdown` |
| `DecileImpact` | Income impacts by decile | FK to baseline/reform sims; `absolute_change`, `relative_change` |
| `ProgramStatistics` | Budget impacts by program | `baseline_total`, `reform_total`, `change` |
| `Poverty` | Poverty rate outputs | `poverty_type`, `headcount`, `rate` |
| `Inequality` | Inequality metrics | `gini`, `top_10_share`, `bottom_50_share` |
| `AggregateOutput` | Custom aggregations | `variable`, `aggregate_type`, `filter_config` |
| `ChangeAggregate` | Change aggregations | baseline vs reform comparison |

---

## API Endpoints

### Registered Routers (`api/__init__.py`)
```
/datasets           - Dataset CRUD + listing
/policies           - Policy CRUD (POST, GET, LIST - no PATCH/DELETE)
/simulations        - Simulation management
/parameters         - Parameter metadata
/parameter-values   - Parameter value CRUD
/variables          - Variable metadata
/dynamics           - Behavioral response configs
/tax-benefit-models - Model listing
/tax-benefit-model-versions - Version listing
/outputs            - Result outputs
/change-aggregates  - Comparison aggregates
/household/*        - Household calculations (async)
/analysis/*         - Economy-wide analysis (async)
/agent/*            - AI agent endpoint (Claude Code)
```

### Key Endpoint Patterns

**Async Pattern** (household, analysis):
```
POST /household/calculate → {"job_id": "...", "status": "pending"}
GET  /household/calculate/{job_id} → poll until status="completed"
```

**CRUD Pattern** (policies, datasets):
```
POST   /policies     - Create
GET    /policies     - List all
GET    /policies/{id} - Get by ID
(PATCH, DELETE - NOT implemented)
```

---

## Modal.com Functions (`modal_app.py`)

| Function | Purpose | Resources |
|----------|---------|-----------|
| `simulate_household_uk` | UK household calc | 4GB RAM, 4 CPU |
| `simulate_household_us` | US household calc | 4GB RAM, 4 CPU |
| `simulate_economy_uk` | UK economy sim | 8GB RAM, 8 CPU |
| `simulate_economy_us` | US economy sim | 8GB RAM, 8 CPU |
| `economy_comparison_uk` | UK decile/budget analysis | 8GB RAM, 8 CPU, 30min timeout |
| `economy_comparison_us` | US decile/budget analysis | 8GB RAM, 8 CPU, 30min timeout |

### Key Feature: Memory Snapshotting
```python
# UK image - uses run_function to snapshot imported modules in memory
uk_image = base_image.run_commands(
    "uv pip install --system policyengine-uk>=2.0.0"
).run_function(_import_uk)  # ← pre-loads uk_latest at build time
```
This enables **sub-1s cold starts** - PolicyEngine models are already loaded in memory.

---

## Database Migrations (`supabase/migrations/`)

| Migration | Purpose |
|-----------|---------|
| `20241119000000_storage_bucket.sql` | Create datasets S3 bucket |
| `20241121000000_storage_policies.sql` | Storage access policies |
| `20251229000000_add_parameter_values_indexes.sql` | Index optimization |
| `20260103000000_add_poverty_inequality.sql` | Poverty/inequality tables |
| `20260108000000_add_simulation_modifier.sql` | Add `simulation_modifier` to policies |

**Note**: Tables are auto-created by SQLModel on app startup, not via migrations. Migrations are only for:
- Storage bucket setup
- Adding indexes
- Schema alterations

---

## Agent Endpoint (`/agent/*`)

An AI-powered policy analysis feature using Claude Code:
- `POST /agent/run` - Start agent with a question
- `GET /agent/logs/{call_id}` - Poll for logs and result
- `GET /agent/status/{call_id}` - Quick status check
- `POST /agent/log/{call_id}` - Modal calls this to stream logs
- `POST /agent/complete/{call_id}` - Modal calls this when done

Runs in:
- **Production**: Modal sandbox
- **Development**: Local background thread

---

## Configuration (`config/settings.py`)

Key settings loaded from environment:
- `DATABASE_URL` - Supabase Postgres connection
- `SUPABASE_URL` / `SUPABASE_KEY` - Supabase client
- `POLICYENGINE_API_URL` - Self-reference URL
- `AGENT_USE_MODAL` - True for production, False for local

---

## Key Design Decisions

1. **Normalized parameter storage** - `parameter_values` table with FKs instead of JSON blobs
2. **Async job pattern** - All heavy calculations return immediately with job_id
3. **Deterministic UUIDs** - Simulations/reports use uuid5 for deduplication
4. **Memory snapshotting** - PolicyEngine models loaded at Modal image build time
5. **SQLModel** - Single source of truth for DB schema and Pydantic validation
6. **simulation_modifier** - Python code injection for custom variable formulas

---

## What's Missing (Gaps)

| Feature | Status |
|---------|--------|
| `PATCH /policies/{id}` | Not implemented |
| `DELETE /policies/{id}` | Not implemented |
| User-policy associations | Not implemented |
| User-simulation associations | Not implemented |
| Authentication | No endpoints exposed |

---

## File Structure

```
src/policyengine_api/
├── api/                    # FastAPI routers
│   ├── __init__.py         # Router registration
│   ├── agent.py            # AI agent endpoint
│   ├── analysis.py         # Economy analysis
│   ├── household.py        # Household calculations
│   ├── policies.py         # Policy CRUD
│   ├── parameters.py       # Parameter metadata
│   ├── parameter_values.py # Parameter values
│   └── ...
├── config/
│   └── settings.py         # Environment config
├── models/                 # SQLModel definitions
│   ├── __init__.py         # Model exports
│   ├── policy.py
│   ├── parameter.py
│   ├── parameter_value.py
│   ├── simulation.py
│   ├── report.py
│   └── ...
├── services/
│   ├── database.py         # DB session management
│   └── storage.py          # Supabase storage client
├── main.py                 # FastAPI app entry point
└── modal_app.py            # Modal serverless functions

supabase/
└── migrations/             # SQL migrations (storage, indexes)

terraform/                  # GCP Cloud Run infrastructure

tests/                      # Pytest tests
```

---

## Development Commands

```bash
make install          # Install dependencies with uv
make dev              # Start supabase + api via docker compose
make test             # Run unit tests
make integration-test # Full integration tests
make format           # Ruff formatting
make lint             # Ruff linting with auto-fix
make modal-deploy     # Deploy Modal.com serverless functions
make init             # Reset tables and storage
make seed             # Populate UK/US models with variables, parameters, datasets
```

---

## Contributors

- **Nikhil Woodruff** - Initial implementation (Nov 2025)
- **Anthony Volk** - Parameter values filtering and indexing (Dec 2025)

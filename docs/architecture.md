# Architecture

The PolicyEngine API v2 is a distributed system for running tax-benefit microsimulations with persistence and async processing.

## Components

### API server

FastAPI application exposing RESTful endpoints for:

- Creating and managing datasets
- Defining policy reforms
- Queueing simulations
- Computing aggregates

The server validates requests, persists to PostgreSQL, and queues background tasks.

### Database

PostgreSQL stores:

- **datasets** - Metadata about microdata files
- **policies** - Serialized parameter reforms
- **simulations** - Execution state and results
- **aggregates** - Computed statistics

Uses SQLModel for type-safe ORM with pydantic integration.

### Worker

Celery workers execute long-running tasks:

- Loading datasets from storage
- Running PolicyEngine simulations
- Computing aggregate statistics
- Storing results to database

Tasks are queued in Redis and processed asynchronously.

## Request flow

1. Client creates simulation via `POST /api/v2/simulations`
2. API validates request and persists simulation record
3. API queues `run_simulation` task in Redis
4. Celery worker picks up task
5. Worker loads dataset and runs PolicyEngine simulation
6. Worker updates simulation status to `completed`
7. Client polls `GET /api/v2/simulations/{id}` to check status
8. Client requests aggregates
9. Worker computes statistics from simulation results

## Data models

All models follow pydantic/SQLModel patterns:

- **Base** - Shared fields
- **Table** - Database model with ID and timestamps
- **Create** - Request schema (no ID)
- **Read** - Response schema (with ID and timestamps)

This ensures type safety across API, database, and business logic.

## Scaling considerations

- **Horizontal API scaling** - Multiple uvicorn workers behind load balancer
- **Worker scaling** - Increase Celery worker count for parallel simulations
- **Database** - PostgreSQL supports read replicas
- **Task queue** - Redis cluster for high availability

## Security

- Database credentials in environment variables
- No hardcoded secrets in codebase
- VPC isolation for AWS deployment
- Security groups limiting network access

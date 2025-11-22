# Example usage

This guide demonstrates a complete workflow using the PolicyEngine API v2.

## Start the services

```bash
docker compose up -d
```

Wait for all services to be healthy:

```bash
docker compose ps
```

## Create a dataset

```bash
curl -X POST http://localhost:8000/api/v2/datasets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "FRS 2023-24",
    "description": "Family Resources Survey representative microdata",
    "filepath": "/data/frs_2023_24_year_2026.h5",
    "year": 2026,
    "tax_benefit_model": "uk_latest"
  }' | jq
```

Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "FRS 2023-24",
  "created_at": "2024-11-19T12:00:00Z",
  ...
}
```

Save the dataset ID for later.

## Create a policy reform

```bash
curl -X POST http://localhost:8000/api/v2/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Increased personal allowance",
    "description": "Raises personal allowance to £15,000",
    "parameter_values": {
      "gov.hmrc.income_tax.allowances.personal_allowance.amount": {
        "2026-01-01": 15000
      }
    }
  }' | jq
```

Save the policy ID.

## Create baseline simulation

```bash
curl -X POST http://localhost:8000/api/v2/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
    "tax_benefit_model": "uk_latest"
  }' | jq
```

The simulation is queued immediately. The worker will process it asynchronously.

## Check simulation status

```bash
curl http://localhost:8000/api/v2/simulations/SIMULATION_ID | jq
```

Poll until status is `completed`:

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "started_at": "2024-11-19T12:01:00Z",
  "completed_at": "2024-11-19T12:05:30Z",
  ...
}
```

## Create aggregates

Calculate total universal credit spending:

```bash
curl -X POST http://localhost:8000/api/v2/outputs/aggregate \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_id": "770e8400-e29b-41d4-a716-446655440000",
    "variable": "universal_credit",
    "aggregate_type": "sum",
    "entity": "benunit"
  }' | jq
```

Calculate mean income in top decile:

```bash
curl -X POST http://localhost:8000/api/v2/outputs/aggregate \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_id": "770e8400-e29b-41d4-a716-446655440000",
    "variable": "household_net_income",
    "aggregate_type": "mean",
    "entity": "household",
    "filter_config": {
      "quantile": 10,
      "quantile_eq": 10
    }
  }' | jq
```

## View results

Get the computed output:

```bash
curl http://localhost:8000/api/v2/outputs/aggregate/OUTPUT_ID | jq
```

Response:

```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "simulation_id": "770e8400-e29b-41d4-a716-446655440000",
  "variable": "universal_credit",
  "aggregate_type": "sum",
  "result": 45000000000.0,
  "created_at": "2024-11-19T12:06:00Z"
}
```

Total UC spending: £45bn

## Python client example

```python
import httpx
import time

BASE_URL = "http://localhost:8000/api/v2"

# Create dataset
dataset = httpx.post(
    f"{BASE_URL}/datasets",
    json={
        "name": "FRS 2023-24",
        "filepath": "/data/frs_2023_24.h5",
        "year": 2026,
        "tax_benefit_model": "uk_latest",
    },
).json()

# Create simulation
simulation = httpx.post(
    f"{BASE_URL}/simulations",
    json={
        "dataset_id": dataset["id"],
        "tax_benefit_model": "uk_latest",
    },
).json()

# Poll for completion
while True:
    sim = httpx.get(f"{BASE_URL}/simulations/{simulation['id']}").json()
    if sim["status"] == "completed":
        break
    elif sim["status"] == "failed":
        raise Exception(f"Simulation failed: {sim['error_message']}")
    time.sleep(5)

# Create aggregate
output = httpx.post(
    f"{BASE_URL}/outputs/aggregate",
    json={
        "simulation_id": simulation["id"],
        "variable": "universal_credit",
        "aggregate_type": "sum",
        "entity": "benunit",
    },
).json()

print(f"Total UC spending: £{output['result'] / 1e9:.1f}bn")
```

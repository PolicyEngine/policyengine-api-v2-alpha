# API reference

Base URL: `http://localhost:8000`

## Datasets

### Create dataset

`POST /datasets`

Request body:

```json
{
  "name": "FRS 2023-24",
  "description": "Family Resources Survey microdata",
  "filepath": "/data/frs_2023_24_year_2026.h5",
  "year": 2026,
  "tax_benefit_model": "uk_latest"
}
```

Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "FRS 2023-24",
  "description": "Family Resources Survey microdata",
  "filepath": "/data/frs_2023_24_year_2026.h5",
  "year": 2026,
  "tax_benefit_model": "uk_latest",
  "created_at": "2024-11-19T12:00:00Z",
  "updated_at": "2024-11-19T12:00:00Z"
}
```

### List datasets

`GET /datasets`

Returns array of dataset objects.

### Get dataset

`GET /datasets/{dataset_id}`

Returns single dataset object.

### Delete dataset

`DELETE /datasets/{dataset_id}`

## Policies

### Create policy

`POST /policies`

Request body:

```json
{
  "name": "Increased personal allowance",
  "description": "Raises PA to £15,000",
  "parameter_values": {
    "gov.hmrc.income_tax.allowances.personal_allowance.amount": {
      "2026-01-01": 15000
    }
  }
}
```

### List policies

`GET /policies`

### Get policy

`GET /policies/{policy_id}`

### Delete policy

`DELETE /policies/{policy_id}`

## Simulations

### Create simulation

`POST /simulations`

Request body:

```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "policy_id": "660e8400-e29b-41d4-a716-446655440000",
  "tax_benefit_model": "uk_latest"
}
```

Response includes status field:

- `pending` - Queued but not started
- `running` - Currently executing
- `completed` - Finished successfully
- `failed` - Error occurred

### List simulations

`GET /simulations`

### Get simulation

`GET /simulations/{simulation_id}`

## Aggregates

### Create aggregate

`POST /aggregates`

Request body:

```json
{
  "simulation_id": "770e8400-e29b-41d4-a716-446655440000",
  "variable": "universal_credit",
  "aggregate_type": "sum",
  "entity": "benunit",
  "filter_config": {
    "quantile": 10,
    "quantile_eq": 5
  }
}
```

Aggregate types:

- `sum` - Total across population
- `mean` - Weighted average
- `count` - Number of entities

### List aggregates

`GET /aggregates`

### Get aggregate

`GET /aggregates/{output_id}`

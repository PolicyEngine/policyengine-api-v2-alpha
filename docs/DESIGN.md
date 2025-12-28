# API hierarchy design

## Levels of analysis

```
┌─────────────────────────────────────────────────────────────┐
│  Level 2: Reports                                           │
│  AI-generated documents, orchestrating multiple jobs        │
│  /reports/*                                                 │
├─────────────────────────────────────────────────────────────┤
│  Level 1: Analyses                                          │
│  Operations on simulations - thin wrappers around           │
│  policyengine package functions                             │
│                                                             │
│  Common (baked-in, trivial to call):                        │
│    /analysis/decile-impact/*                                │
│    /analysis/budget-impact/*                                │
│    /analysis/winners-losers/*                               │
│                                                             │
│  Flexible (configurable):                                   │
│    /analysis/compare/*                                      │
├─────────────────────────────────────────────────────────────┤
│  Level 0: Simulations                                       │
│  Single world-state calculations                            │
│  /simulate/household                                        │
│  /simulate/economy                                          │
└─────────────────────────────────────────────────────────────┘
```

All operations are **async** (Modal compute). The API is a thin orchestration layer - all analysis logic lives in the `policyengine` package.

## Mapping to policyengine package

| API endpoint | policyengine function |
|--------------|----------------------|
| `/simulate/household` | `calculate_household_impact()` |
| `/simulate/economy` | `Simulation.run()` |
| `/analysis/decile-impact/*` | `calculate_decile_impacts()` |
| `/analysis/budget-impact/*` | `ProgrammeStatistics` |
| `/analysis/winners-losers/*` | `ChangeAggregate` with filters |
| `/analysis/compare/*` | `economic_impact_analysis()` or custom |

## Level 0: Simulations

### `/simulate/household`

Single household calculation. Wraps `policyengine.tax_benefit_models.uk.analysis.calculate_household_impact()`.

```
POST /simulate/household
{
  "model": "policyengine_uk",
  "household": {
    "people": [{"age": 30, "employment_income": 50000}],
    "benunit": {},
    "household": {}
  },
  "year": 2026,
  "policy_id": null
}

→ Returns job_id, poll for results
```

### `/simulate/economy`

Population simulation. Creates and runs a `policyengine.core.Simulation`.

```
POST /simulate/economy
{
  "model": "policyengine_uk",
  "dataset_id": "...",
  "policy_id": null,
  "dynamic_id": null
}

→ Returns simulation_id, poll for results
```

Economy simulations are **deterministic and cached** by (dataset_id, model_version, policy_id, dynamic_id).

## Level 1: Analyses - Common (baked-in)

These are the bread-and-butter analyses. Trivial to call, no configuration needed.

### `/analysis/decile-impact/economy`

Income decile breakdown. Wraps `calculate_decile_impacts()`.

```
POST /analysis/decile-impact/economy
{
  "model": "policyengine_uk",
  "dataset_id": "...",
  "baseline_policy_id": null,
  "reform_policy_id": "..."
}

→ Returns job_id

GET /analysis/decile-impact/economy/{job_id}
→ Returns:
{
  "status": "completed",
  "deciles": [
    {"decile": 1, "baseline_mean": 15000, "reform_mean": 15500, "change": 500, "pct_change": 3.3, ...},
    {"decile": 2, ...},
    ...
    {"decile": 10, ...}
  ]
}
```

### `/analysis/budget-impact/economy`

Tax and benefit programme totals. Wraps `ProgrammeStatistics`.

```
POST /analysis/budget-impact/economy
{
  "model": "policyengine_uk",
  "dataset_id": "...",
  "baseline_policy_id": null,
  "reform_policy_id": "..."
}

→ Returns job_id

GET /analysis/budget-impact/economy/{job_id}
→ Returns:
{
  "status": "completed",
  "net_budget_impact": -20000000000,
  "programmes": [
    {"name": "income_tax", "is_tax": true, "baseline_total": 200e9, "reform_total": 180e9, "change": -20e9},
    {"name": "universal_credit", "is_tax": false, "baseline_total": 50e9, "reform_total": 52e9, "change": 2e9},
    ...
  ]
}
```

### `/analysis/winners-losers/economy`

Who gains and loses. Wraps `ChangeAggregate` with change filters.

```
POST /analysis/winners-losers/economy
{
  "model": "policyengine_uk",
  "dataset_id": "...",
  "baseline_policy_id": null,
  "reform_policy_id": "...",
  "threshold": 0  // Change threshold (default: any change)
}

→ Returns job_id

GET /analysis/winners-losers/economy/{job_id}
→ Returns:
{
  "status": "completed",
  "winners": {"count": 15000000, "mean_gain": 500},
  "losers": {"count": 5000000, "mean_loss": -200},
  "unchanged": {"count": 30000000}
}
```

### `/analysis/decile-impact/household`

Compare household across scenarios by artificial decile assignment.

```
POST /analysis/decile-impact/household
{
  "model": "policyengine_uk",
  "household": {"people": [{"employment_income": 50000}]},
  "year": 2026,
  "baseline_policy_id": null,
  "reform_policy_id": "..."
}

→ Returns which decile this household falls into and their change
```

## Level 1: Analyses - Flexible

### `/analysis/compare/economy`

Full comparison with all outputs. Wraps `economic_impact_analysis()`.

```
POST /analysis/compare/economy
{
  "model": "policyengine_uk",
  "dataset_id": "...",
  "scenarios": [
    {"label": "baseline"},
    {"label": "reform", "policy_id": "..."},
    {"label": "reform_dynamic", "policy_id": "...", "dynamic_id": "..."}
  ]
}

→ Returns job_id

GET /analysis/compare/economy/{job_id}
→ Returns:
{
  "status": "completed",
  "scenarios": {...simulation results...},
  "comparisons": {
    "reform": {
      "relative_to": "baseline",
      "decile_impacts": [...],
      "budget_impact": {...},
      "winners_losers": {...}
    },
    "reform_dynamic": {...}
  }
}
```

### `/analysis/compare/household`

Compare multiple scenarios for a household.

```
POST /analysis/compare/household
{
  "model": "policyengine_uk",
  "household": {...},
  "year": 2026,
  "scenarios": [
    {"label": "baseline"},
    {"label": "reform", "policy_id": "..."}
  ]
}

→ Returns all scenario results + computed differences
```

### `/analysis/aggregate/economy` (power user)

Custom aggregation with full filter control. Directly exposes `Aggregate` / `ChangeAggregate`.

```
POST /analysis/aggregate/economy
{
  "model": "policyengine_uk",
  "dataset_id": "...",
  "simulation_id": "...",  // or policy_id to create
  "variable": "household_net_income",
  "aggregate_type": "mean",
  "entity": "household",
  "filters": {
    "quantile": {"variable": "household_net_income", "n": 10, "eq": 1}
  }
}

→ Returns single aggregate value
```

## Adding new analysis types

To add a new common analysis (e.g. marginal tax rates):

1. **policyengine package**: Add `MarginalTaxRate` output class and `calculate_marginal_rates()` function
2. **API**: Add `/analysis/marginal-rates/*` endpoint that wraps the function
3. **Modal**: Add function to run it

The API endpoint is ~20 lines - just parameter parsing and calling the policyengine function.

## URL structure summary

```
# Level 0: Simulations
POST /simulate/household
GET  /simulate/household/{job_id}
POST /simulate/economy
GET  /simulate/economy/{simulation_id}

# Level 1: Common analyses (baked-in, trivial)
POST /analysis/decile-impact/economy
GET  /analysis/decile-impact/economy/{job_id}
POST /analysis/budget-impact/economy
GET  /analysis/budget-impact/economy/{job_id}
POST /analysis/winners-losers/economy
GET  /analysis/winners-losers/economy/{job_id}

# Level 1: Flexible analyses
POST /analysis/compare/economy
GET  /analysis/compare/economy/{job_id}
POST /analysis/compare/household
GET  /analysis/compare/household/{job_id}
POST /analysis/aggregate/economy
GET  /analysis/aggregate/economy/{job_id}

# Level 2: Reports (future)
POST /reports/policy-impact
GET  /reports/policy-impact/{report_id}
```

## Use cases

| Use case | Endpoint |
|----------|----------|
| My tax under current law | `/simulate/household` |
| Reform impact on my household | `/analysis/compare/household` with 2 scenarios |
| Revenue impact of reform | `/analysis/budget-impact/economy` |
| Decile breakdown of reform | `/analysis/decile-impact/economy` |
| Who wins and loses | `/analysis/winners-losers/economy` |
| Full reform analysis | `/analysis/compare/economy` |
| Compare 3 reform proposals | `/analysis/compare/economy` with 4 scenarios |
| Static vs dynamic comparison | `/analysis/compare/economy` with 3 scenarios |
| Custom aggregation | `/analysis/aggregate/economy` |

## Migration

Deprecate existing endpoints:
- `/household/calculate` → `/simulate/household`
- `/household/impact` → `/analysis/compare/household`
- `/analysis/economic-impact` → `/analysis/compare/economy`

## Implementation notes

1. All Modal functions import from `policyengine` package
2. API endpoints do minimal work: parse request, call Modal, store results
3. New analysis types require:
   - Add to policyengine package (logic)
   - Add API endpoint (orchestration)
   - Add Modal function (compute)

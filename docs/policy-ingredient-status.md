# Policy Ingredient Status in API v2 Alpha

This document summarizes the current state of the policy ingredient implementation in `policyengine-api-v2-alpha`, compares it to API v1, and outlines gaps and recommendations for migration.

## Current Implementation

### Database Tables

The policy system uses a normalized relational model with two main tables:

#### `policies` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key, auto-generated |
| `name` | str | Policy name (required) |
| `description` | str \| None | Optional description |
| `simulation_modifier` | str \| None | Python code for custom variable formulas |
| `created_at` | datetime | Auto-generated UTC timestamp |
| `updated_at` | datetime | Auto-generated UTC timestamp |

#### `parameter_values` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `parameter_id` | UUID | FK to `parameters` table |
| `policy_id` | UUID \| None | FK to `policies` (NULL = baseline/current law) |
| `dynamic_id` | UUID \| None | FK to `dynamics` table |
| `value_json` | Any | The actual parameter value (JSON) |
| `start_date` | datetime | Effective start date |
| `end_date` | datetime \| None | Effective end date |
| `created_at` | datetime | Auto-generated |

**Key design:** `parameter_values` stores BOTH baseline values (`policy_id IS NULL`) AND reform values (`policy_id = <reform_uuid>`). Each policy is self-contained with its own set of parameter value overrides - this is intentional, not a normalization issue. When running simulations, baseline (NULL) vs reform (policy_id = X) values are compared to compute impacts.

### Supporting Tables

#### `parameters` table (metadata)
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | str | Parameter path (e.g., `gov.irs.ctc.max`) |
| `label` | str \| None | Human-readable label |
| `description` | str \| None | Documentation |
| `data_type` | str \| None | Value type |
| `unit` | str \| None | Unit of measurement |
| `tax_benefit_model_version_id` | UUID | FK to model version |
| `created_at` | datetime | Auto-generated |

#### `tax_benefit_models` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | str | Country identifier ("uk" or "us") |
| `description` | str \| None | Optional |
| `created_at` | datetime | Auto-generated |

### API Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `POST` | `/policies` | ✅ Implemented | Create policy with parameter values |
| `GET` | `/policies` | ✅ Implemented | List all policies |
| `GET` | `/policies/{id}` | ✅ Implemented | Get policy by ID |
| `PATCH` | `/policies/{id}` | ❌ Missing | Update policy |
| `DELETE` | `/policies/{id}` | ❌ Missing | Delete policy |

### Files

| File | Purpose |
|------|---------|
| `src/policyengine_api/models/policy.py` | SQLModel definitions |
| `src/policyengine_api/models/parameter_value.py` | Parameter value model |
| `src/policyengine_api/api/policies.py` | Policy router/endpoints |
| `src/policyengine_api/api/parameter_values.py` | Parameter values router |
| `tests/test_policies.py` | Basic CRUD tests |

### Contributors

- **Nikhil Woodruff** - Initial implementation (Nov 2025)
- **Anthony Volk** - Added parameter_values filtering and indexing (Dec 2025)

---

## Comparison: API v1 vs API v2 Alpha

### URL Structure

| Aspect | API v1 | API v2 Alpha |
|--------|--------|--------------|
| Create | `POST /{country_id}/policy` | `POST /policies` |
| Get | `GET /{country_id}/policy/{id}` | `GET /policies/{id}` |
| List | `GET /{country_id}/policies` | `GET /policies` |

**Key difference:** v1 has country in URL path; v2 does not.

### Country Handling

| API v1 | API v2 Alpha |
|--------|--------------|
| Country in URL path (`/us/policy/123`) | Country determined by `tax_benefit_model_name` in request body |
| `@validate_country` decorator | No explicit country validation on policy endpoints |
| Policy implicitly scoped to country | Policy is country-agnostic; country context from analysis request |

### Policy Storage

| API v1 | API v2 Alpha |
|--------|--------------|
| `policy_hash` - hash of JSON blob | `parameter_values` - relational FK to parameters |
| Policy content stored as JSON | Policy content normalized in separate table |
| Embedded values in metadata response | Separate queries for parameter values |

### Metadata Response (Parameters)

**API v1 - Embedded values:**
```json
{
  "gov.irs.ctc.max": {
    "type": "parameter",
    "label": "CTC maximum",
    "values": {
      "2024-01-01": 2000,
      "2023-01-01": 2000,
      "2022-01-01": 2000
    }
  }
}
```

**API v2 Alpha - Normalized:**
```
-- parameters table
id | name           | label
1  | gov.irs.ctc.max | CTC maximum

-- parameter_values table
id | parameter_id | start_date  | value_json | policy_id
1  | 1            | 2024-01-01  | 2000       | NULL (baseline)
2  | 1            | 2024-01-01  | 3000       | <reform_id>
```

### User Associations

| API v1 | API v2 Alpha |
|--------|--------------|
| `user_policies` table exists in code | Not implemented |
| Endpoints NOT exposed (dead code) | No user association tables/endpoints |
| Fields: `user_id`, `reform_id`, `baseline_id`, `year`, `geography`, etc. | N/A |

---

## Pros and Cons

### API v2 Alpha Advantages

| Pro | Explanation |
|-----|-------------|
| **Normalized schema** | Easier to query specific parameter changes without parsing JSON |
| **Relational integrity** | FK constraints ensure valid parameter references |
| **Better indexing** | Can index on `parameter_id`, `policy_id`, `start_date` |
| **Audit trail** | Each parameter value has its own `created_at` |
| **Cleaner reform diffs** | Query `WHERE policy_id = X` to see all reform changes |

### API v2 Alpha Disadvantages

| Con | Explanation |
|-----|-------------|
| **No country on policy** | Can't filter policies by country at DB level |
| **No user associations** | Must be built from scratch |
| **Missing PATCH/DELETE** | Incomplete CRUD |
| **No label field** | Only `name` + `description`, no user-friendly `label` |
| **More complex queries** | JOIN required to get policy with values |

### API v1 Advantages

| Pro | Explanation |
|-----|-------------|
| **Country in URL** | Clear API contract, easy filtering |
| **Simple storage** | Policy is a single JSON blob |
| **User associations designed** | Schema exists (though not exposed) |

### API v1 Disadvantages

| Con | Explanation |
|-----|-------------|
| **JSON blob parsing** | Must parse to query specific parameters |
| **No referential integrity** | Policy JSON could reference invalid parameters |
| **Harder to diff** | Must compare two JSON blobs to see changes |

---

## Gaps for Migration

### Must Have

1. **User associations table and endpoints**
   - `user_policies` table with `user_id`, `policy_id`, `label`, `created_at`
   - `POST /user-policies` - Create association
   - `GET /user-policies?user_id=X` - List user's policies
   - `DELETE /user-policies/{id}` - Remove association

2. **PATCH endpoint for policies**
   - Update `name`, `description`
   - Update parameter values

3. **DELETE endpoint for policies**
   - Cascade delete parameter values

### Should Have

4. **Country validation**
   - Either add `country_id` to policy model OR
   - Validate at creation that all parameter_ids belong to same country

5. **Label field on policy**
   - User-friendly display name separate from `name`

### Nice to Have

6. **Soft delete**
   - `deleted_at` field instead of hard delete

7. **Policy versioning**
   - Track changes over time

---

## Suggested Schema Changes

### Option A: Add country_id to Policy

```python
class Policy(PolicyBase, table=True):
    # ... existing fields ...
    country_id: str  # "us" or "uk"
```

**Pros:** Simple filtering, matches v1 pattern
**Cons:** Redundant with parameter → tax_benefit_model → name

### Option B: Derive country from parameters (current approach)

Keep as-is, derive country from first parameter's tax_benefit_model.

**Pros:** No schema change, DRY
**Cons:** Requires JOIN to filter by country

### Recommendation: Option A

Add explicit `country_id` for simpler queries and clearer data model.

---

## Next Steps

1. [ ] Add `country_id` to Policy model
2. [ ] Add `label` field to Policy model
3. [ ] Create UserPolicy model and table
4. [ ] Implement `PATCH /policies/{id}` endpoint
5. [ ] Implement `DELETE /policies/{id}` endpoint
6. [ ] Implement user policy association endpoints
7. [ ] Add database migration for schema changes
8. [ ] Update tests

---

## References

- Policy model: `src/policyengine_api/models/policy.py`
- Policy router: `src/policyengine_api/api/policies.py`
- Parameter value model: `src/policyengine_api/models/parameter_value.py`
- Tests: `tests/test_policies.py`

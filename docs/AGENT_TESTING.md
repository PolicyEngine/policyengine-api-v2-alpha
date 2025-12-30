# Agent testing and optimisation

This document tracks ongoing work to test and improve the PolicyEngine agent's ability to answer policy questions efficiently.

## Goal

Minimise the number of turns the agent needs to answer policy questions by improving API metadata, documentation, and structure - not by hacking for specific test cases.

## Test categories

We want comprehensive coverage across:
- **Country**: UK and US
- **Scope**: Household (single family) and Economy (population-wide)
- **Complexity**: Simple (single variable lookup) to Complex (multi-step reforms)

## Example questions to test

### UK Household (simple)
- "What is my income tax if I earn £50,000?"
- "How much child benefit would a family with 2 children receive?"

### UK Household (complex)
- "Compare my net income under current law vs if the basic rate was 25%"
- "What's the marginal tax rate for someone earning £100,000?"

### UK Economy (simple)
- "What's the total cost of child benefit?"
- "How many people pay higher rate tax?"

### UK Economy (complex)
- "What would be the budgetary impact of raising the personal allowance to £15,000?"
- "How would a £500 UBI affect poverty rates?"

### US Household (simple)
- "What is my federal income tax if I earn $75,000?"
- "How much SNAP would a family of 4 with $30,000 income receive?"

### US Household (complex)
- "Compare my benefits under current law vs doubling the EITC"
- "What's my marginal tax rate including state taxes in California?"

### US Economy (simple)
- "What's the total cost of SNAP?"
- "How many households receive the EITC?"

### US Economy (complex)
- "What would be the budgetary impact of expanding the Child Tax Credit to $3,600?"
- "How would eliminating the SALT cap affect different income deciles?"

## Current agent architecture

The agent uses Claude Code in a Modal sandbox with:
- System prompt containing API documentation (see `src/policyengine_api/prompts/`)
- Direct HTTP calls via curl to the PolicyEngine API
- No MCP (it was causing issues in Modal containers)

## Optimisation strategies

1. **Improve system prompt** - Make API usage clearer, provide more examples
2. **Add API response examples** - Show what successful responses look like
3. **Parameter documentation** - Ensure all parameters are well-documented with valid values
4. **Error messages** - Make error messages actionable so agent can self-correct
5. **Endpoint discoverability** - Help agent find the right endpoint quickly

## Test file location

Tests are in `tests/test_agent_policy_questions.py` (integration tests requiring Modal).

## How to continue this work

1. Run existing tests: `pytest tests/test_agent_policy_questions.py -v -s`
2. Check agent logs in Logfire for turn counts and errors
3. Identify common failure patterns
4. Improve prompts/metadata to address failures
5. Add new test cases as coverage expands

## Observed issues

### Issue 1: Parameter search doesn't filter by country (9 turns for personal allowance)

**Problem**: When searching for "personal allowance", the agent gets US results (Illinois AABD) mixed with UK results. It took 9 turns to find the UK personal allowance.

**Agent's failed searches**:
1. "personal allowance" → Illinois AABD (US)
2. "income tax personal allowance" → empty
3. "income_tax" → US CBO parameters
4. "basic rate" → UK CGT (closer!)
5. "allowance" → California SSI (US)
6. "hmrc income_tax allowances personal" → empty
7. "hmrc.income_tax.allowances" → found it!

**Solution implemented**:
- Added `tax_benefit_model_name` filter to `/parameters/` endpoint
- Updated system prompt to instruct agent to use country filter

**NOT acceptable solutions** (test hacking):
- Adding specific parameter name examples to system prompt
- Telling agent exactly what to search for

### Issue 2: Duplicate parameters in database

**Problem**: Same parameter name exists with multiple IDs. One has values, one doesn't. Agent picks wrong one first.

**Example**: `gov.hmrc.income_tax.allowances.personal_allowance.amount` has two entries with different IDs.

**Solution needed**: Data cleanup - deduplicate parameters in seed script.

### Issue 3: Variables endpoint lacks search

**Problem**: `/variables/` had no search or country filter. Agent can't discover variable names.

**Solution implemented**: Added `search` and `tax_benefit_model_name` filters to `/variables/`.

### Issue 4: Datasets endpoint lacks country filter

**Problem**: `/datasets/` returned all datasets, mixing UK and US.

**Solution implemented**: Added `tax_benefit_model_name` filter to `/datasets/`.

## Baseline measurements (production API, before improvements)

| Question type | Turns | Target | Notes |
|---------------|-------|--------|-------|
| Parameter lookup (UK personal allowance) | 9-10 | 3-4 | No country filter, mixed UK/US results |
| Household calculation (UK £50k income) | 6 | 5-6 | Efficient, includes 2 polling turns |

## Progress log

- 2024-12-30: Initial setup, created test framework and first batch of questions
- 2024-12-30: Tested personal allowance lookup - 9 turns (target: 3-4). Root cause: no country filter on parameter search
- 2024-12-30: Added `tax_benefit_model_name` filter to `/parameters/`, `/variables/`, `/datasets/`
- 2024-12-30: Tested household calc - 6 turns (acceptable). Async polling is the overhead
- 2024-12-30: Discovered duplicate parameters in DB causing extra turns

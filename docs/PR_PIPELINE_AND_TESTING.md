# PR Pipeline and Testing

Current state of PR checks, test coverage, git tagging, and recommendations for policyengine.py and API v2 alpha.

## Current state

### policyengine.py

**PR checks:** Ruff lint + pytest (Python 3.13 + 3.14 matrix, macOS only). No format check, no type checking, no coverage reporting, no build verification.

**Test coverage:** 22 test files exist. No coverage measurement configured — no `pytest-cov`, no `--cov` flags, no coverage config. Actual coverage percentage is unknown.

**Git tagging:** Broken. Only 1 tag (`0.1.1`) despite being at version 3.2.0. Zero GitHub Releases. The versioning workflow (`versioning.yml`) watches `changelog_entry.yaml` but the project migrated to towncrier `changelog.d/` fragments, so the trigger likely never fires.

**Release flow:** Merge → `push.yml` runs towncrier (bumps version, compiles changelog, commits) → re-triggered push runs tests → publishes to PyPI. Works, but no git tag or GitHub Release is created.

### API v2 alpha

**PR checks:** `pytest -v -m "not integration"` only. No linting, no formatting, no type checking in CI. The deploy workflow's test job runs only `pytest tests/test_models.py -v` — a subset.

**Test coverage:** 36 test files, ~8,222 lines, 242+ test items. No coverage measurement configured.

**Git tagging:** Completely absent. Zero tags. Version hardcoded at `0.1.0`, never bumped. No release automation.

### Summary

| | policyengine.py | API v2 alpha |
|---|---|---|
| PR lint/format | Lint only | None |
| PR type checking | None | None |
| PR tests | pytest (3.13 + 3.14) | pytest (non-integration) |
| Coverage measurement | None | None |
| Git tags | 1 (stale) | 0 |
| GitHub Releases | 0 | 0 |
| Current version | 3.2.0 | 0.1.0 |
| Auto-tagging | Broken | Non-existent |

## Recommendations

### policyengine.py (library)

1. **Add format check to PR.** `ruff format --check .` alongside the existing `ruff check .`.

2. **Add mypy --strict.** Tax-benefit calculation libraries benefit from rigorous type safety. Start with `--strict` on new code, gradually expand.

3. **Add coverage measurement.** Install `pytest-cov`, add `--cov=policyengine --cov-fail-under=80` to CI. Measure current state first, then set floor.

4. **Property-based testing with Hypothesis.** Tax-benefit calculations have mathematical invariants (net income <= gross income, benefits decrease past thresholds). Hypothesis generates random household configurations to test these properties.

5. **Fix git tagging with python-semantic-release.** Replace broken towncrier versioning trigger. Reads conventional commits, bumps version, creates git tags, creates GitHub Releases, publishes to PyPI.

6. **Add ubuntu to test matrix.** Currently macOS only. Add ubuntu-latest to match deployment targets. Consider Python 3.10–3.12 for downstream compatibility.

7. **Add build verification.** `uv build` in PR checks to catch packaging issues before merge.

### API v2 alpha (service)

1. **Add linting and formatting to PR checks.** `ruff check .` and `ruff format --check .`. Already in dev dependencies, just not in CI.

2. **Run full test suite in deploy workflow.** Change `pytest tests/test_models.py -v` to `pytest -v -m "not integration"` at minimum.

3. **Add coverage measurement.** Install `pytest-cov`, measure current state, set floor at 75%.

4. **Real Postgres in CI.** Use `services: postgres` in GitHub Actions for integration tests. Transaction rollback pattern (begin at test start, rollback at end) for isolation.

5. **Mock at the service boundary.** Modal functions mocked at the service layer, not HTTP level. Tests verify job creation and response handling without calling Modal.

6. **OpenAPI schema diffing.** Detect breaking API changes in PRs. Generate schema from the app, diff against `main`, flag breaking changes.

7. **Post-deploy smoke tests.** Expand beyond canary health check to hit key endpoints (`/metadata`, a simple household simulation).

8. **Adopt python-semantic-release when leaving alpha.** Bumps version, tags commits, creates GitHub Releases. For now, at minimum add a manual workflow for version bumps.

## Proposed staging pipeline (API v2 alpha)

The current deploy pipeline goes straight from merge to production. The `policyengine-api-v2` (non-alpha) repo already implements a staging pattern using Modal environments. Here's the proposed adaptation for the alpha repo, which also manages Cloud Run and Terraform.

### Architecture

```
PR merge to main
        │
        ▼
  ┌───────────┐
  │   Test     │  (unit tests + lint)
  └─────┬─────┘
        │
  ┌─────┼──────────────┐
  ▼     ▼              ▼
migrate build          infra         (parallel)
  │     │              │
  └──┬──┘──────────────┘
     ▼
  Deploy to staging
  ├─ Modal: modal deploy --env=staging
  └─ Cloud Run: --tag=staging --no-traffic
     │
     ▼
  Integration tests against staging URL
     │
     ├── Pass → Deploy to production
     │   ├─ Modal: modal deploy --env=main
     │   └─ Cloud Run: shift traffic to latest
     │
     └── Fail → Stop. Staging has no traffic, production unaffected.
```

### How it works

**Modal environments**: Modal natively supports isolated environments. Each environment has its own Secrets and object lookups. Deploy to staging with `modal deploy --env=staging`, to production with `modal deploy --env=main`. The `settings.modal_environment` field (already exists in `config/settings.py`) controls which Modal environment the API routes computation to.

**Cloud Run tagged revisions**: Cloud Run supports deploying revisions with zero traffic. Deploy a staging revision with `--tag=staging --no-traffic` — it gets a unique URL (`https://staging---service-abc.a.run.app`) for testing without affecting production traffic. Only after integration tests pass does the workflow shift traffic to the new revision.

**Terraform**: No changes needed. The same Cloud Run service handles both staging (tagged revision, no traffic) and production (latest revision with traffic). Terraform manages the service definition, not individual revisions.

**Database**: Same Supabase database for both environments. Integration tests should be non-destructive (read-only queries or create-then-cleanup). A separate Supabase project can be provisioned later if full isolation is needed.

**GitHub Environments**: Create a `staging` environment in repo settings alongside `production`. Each environment can have its own secrets and deployment protection rules.

### Integration tests against staging

The existing `tests/test_integration.py` uses direct database access. For the staging pipeline, a new test file (`tests/test_integration_api.py`) would make HTTP requests to the deployed staging URL via an `API_BASE_URL` environment variable. Tests should cover: health check, listing models/parameters/variables, creating and polling a household simulation.

### Key differences from policyengine-api-v2

| Aspect | API v2 (non-alpha) | API v2 alpha |
|--------|---------------------|--------------|
| Compute | Modal only | Modal + Cloud Run |
| Infra management | None (Modal handles) | Terraform |
| Image build | Not needed | Docker + Artifact Registry |
| Staging isolation | Modal environment | Modal env + Cloud Run tagged revision |
| Database | Not managed | Alembic migrations |
| Reusable workflow | Yes (modal-deploy.reusable.yml) | Could extract later |

### Rollback

If integration tests fail after staging deployment:
- Cloud Run: Staging revision has no traffic — production is unaffected. Do not proceed.
- Modal: Staging environment is isolated from `main`. No rollback needed.
- The workflow uses `needs: [integration-test]` on production deploy jobs, so failures block production automatically.

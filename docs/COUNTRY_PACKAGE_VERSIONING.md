# Country Package Versioning

How country package versions (policyengine-us, policyengine-uk) are managed across the PolicyEngine stack, and proposed improvements for the v2 API.

## Current state across systems

### policyengine-us release flow

1. Developer merges PR to `main` (must include a towncrier changelog fragment in `changelog.d/`)
2. `push.yaml` versioning job reads fragment types to infer semver bump (breaking → major, added/removed → minor, else → patch)
3. Bumps version in `pyproject.toml`, compiles `CHANGELOG.md` via towncrier, commits as `"Update PolicyEngine US"`
4. Second push triggers full test suite (4 parallel jobs), then publishes to PyPI
5. `Deploy` job runs `.github/update_api.py`, which creates automated PRs in downstream repos

This happens ~3-4 times per day. policyengine-us is currently at v1.595.0. policyengine-uk follows the same pattern at a lower cadence (v2.74.0).

### API v1 (policyengine-api)

**Version pinning:** Exact pins in `pyproject.toml` (`policyengine_us==1.595.0`).

**Automated PR flow:**
1. policyengine-us's `update_api.py` sleeps 5 minutes (PyPI propagation), clones policyengine-api, runs `gcp/bump_country_package.py`
2. Script updates the version pin, writes a changelog entry, creates branch `bump-policyengine-us-to-X.Y.Z`, opens a PR
3. PR runs CI (lint, Docker build, PyPI availability check, tests)
4. Manual merge triggers deploy to App Engine

**Cache invalidation:** Every database table (`household`, `computed_household`, `policy`, `economy`, `reform_impact`, `simulations`, etc.) has an `api_version` column. The version is read at import time via `importlib.metadata`. When querying for cached results, the current package version is part of the filter — old results are silently bypassed, new computations are triggered on demand. No re-seeding or migration required.

**Dataset references:** Hardcoded HuggingFace URLs (`hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5`). `get_dataset_version()` returns `None` for all countries, delegating to policyengine.py's defaults.

### App v2 (policyengine-app, main branch)

- Calls `GET /{country}/metadata` on load to learn the current country package version
- Passes `version={metadata.version}` on economy API calls (used as cache key, not user-selectable)
- Dataset selection exists in URL parameters (`?dataset=enhanced_cps`) but there is no UI for it
- Saves `api_version` and `dataset` alongside user policy records for tracking

### API v2 alpha (this repo)

**Version pinning:** Loose constraints everywhere.
- `pyproject.toml`: `policyengine-us>=1.0.0`, `policyengine-uk>=2.0.0`
- `modal_app.py`: same `>=` constraints in pip install commands
- `policyengine.py`: pinned to git branch (`app-v2-migration`), not a version

**No automated notifications:** policyengine-us's `update_api.py` only targets v1 and policyengine-household-api. v2 is not in the list.

**Version tracking:** `TaxBenefitModelVersion` table stores a string (`"latest"`) — not the actual semver. Simulations reference this, but there's no record of which package version produced the results.

**Datasets:** Seeded with name/year/filepath but no record of which package version generated them or which version they're compatible with.

**Single version per deployment:** Modal images bake in one version of each country package. No ability to run multiple versions simultaneously.

## Gaps in v2

1. **No awareness of new country package releases.** Deployments are manual and version selection is accidental (whatever pip resolves at build time).

2. **No version lineage.** Can't answer "which policyengine-us version produced this simulation?" or "which package version generated this dataset?"

3. **No cache invalidation strategy.** v1's `api_version` column pattern is not implemented. Stale results from an old package version are indistinguishable from current results.

4. **Datasets are opaque.** Users can't see what dataset versions are available, when they were generated, or choose between them.

5. **Updating a country package requires full redeploy.** Rebuild Modal images, re-seed database, redeploy everything. No incremental path.

6. **policyengine.py is pinned to a branch, not a version.** Non-deterministic builds — the same branch can resolve to different commits on different days.

## Proposed approaches

### A: Automated version-bump PRs (v1 pattern, adapted)

Add `policyengine-api-v2-alpha` to policyengine-us's `update_api.py`. When a new version publishes, a PR is created updating version pins in `pyproject.toml` and `modal_app.py`. Manual merge triggers deploy.

- Pros: Familiar pattern, explicit version tracking, human gate
- Cons: 3-4 PRs/day for US alone, manual merge bottleneck, still requires full Modal image rebuild, doesn't solve dataset versioning
- Best for: Quick win to close the "v2 doesn't know about new versions" gap

### B: Version registry with on-demand Modal image builds

Track installed country package versions per Modal deployment in a `package_versions` table. When a new package publishes, a workflow (triggered by `repository_dispatch` from policyengine-us) updates the registry and rebuilds Modal images tagged by version (`us_image_1_595_0`). The API routes requests to the correct version. Old deployments coexist during transition.

- Pros: Decouples API deploys from package updates, enables multiple simultaneous versions, explicit tracking
- Cons: More complex, need to manage multiple Modal deployments, higher cost if keeping old versions warm
- Best for: Version rollback or A/B testing of country package changes

### C: Version-aware database + cache invalidation (v1 pattern, modernized)

Store the actual installed policyengine-us/uk semver in `TaxBenefitModelVersion` (replace `"latest"` with real versions). Add `country_package_version` to simulation results. Use version as a cache key in queries. Expose current versions via `/metadata`.

- Pros: Proven pattern from v1, results are automatically version-scoped, no need to clean old data
- Cons: Doesn't solve "when to trigger a deploy", doesn't enable multiple simultaneous versions
- Best for: Essential foundational layer regardless of other choices

### D: Dataset versioning and user-facing selection

Add `version` and `generated_with_package_version` fields to the `Dataset` model. Add `is_default` boolean. Expose `GET /datasets/?country=us` with version metadata. App renders a dataset picker in report setup UI.

- Pros: User-facing transparency, reproducibility, supports the in-review PR for adding datasets to the database
- Cons: UI work needed, need a retention policy for old dataset versions
- Best for: When datasets should be a first-class user-facing concept

### E: Event-driven pipeline (fully automated)

policyengine-us publishes to PyPI → sends `repository_dispatch` to v2. A dedicated `country-package-update.yml` workflow updates version pins, runs tests, rebuilds Modal images, updates version records in the database. Does not redeploy Cloud Run. A separate `dataset-update.yml` handles dataset regeneration independently.

- Pros: Fully automated, decouples API code changes from model updates, no manual merge bottleneck
- Cons: Most complex, requires trust in automated testing, needs robust rollback
- Best for: Long-term target once test coverage and version tracking are solid

## Recommended implementation order

1. **C** — Version-aware database. Foundational, needed regardless. Real semvers in `TaxBenefitModelVersion`, version on simulation results, `/metadata` endpoint.
2. **A** — Automated version-bump PRs. Quick to implement (modify `update_api.py` in policyengine-us/uk). Immediate visibility into new versions.
3. **D** — Dataset versioning. Builds on the in-review dataset PR. Version + lineage fields, exposed to the app.
4. **E** — Event-driven pipeline. Once test suite is trusted and version tracking is in place, automate the full flow and drop the PR-based approach.

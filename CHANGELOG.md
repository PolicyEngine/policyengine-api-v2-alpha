0.6.4 (2026-04-17)

# Fixed

- Agent callback endpoints (`/agent/log/{call_id}`, `/agent/complete/{call_id}`) now require HMAC-signed call IDs and store state in bounded TTLCaches to prevent log injection and unbounded memory growth. All reads and writes to the TTLCaches are serialised behind a `threading.Lock` so the asyncio event-loop thread and the background executor thread (`_run_local_agent`) cannot corrupt the cache under concurrent access. Server startup now emits a warning when `AGENT_CALLBACK_SECRET` falls back to a per-process random value (a multi-worker hazard). Country variable-type catalogs used by household validation are cached per `TaxBenefitModelVersion` to avoid re-querying an immutable catalog on every request. (#265)
- Unified the agent turn limit under a single `DEFAULT_AGENT_MAX_TURNS` constant so local and Modal entry points no longer diverge (previously 100 vs 30). (#266)
- `/analysis/rerun/{report_id}` now requires an `X-API-Key` header; the endpoint is destructive (deletes result records) and was previously reachable anonymously. (#267)
- Household payload models now cap entity groups at 1000 entries and 500 keys per entity to prevent OOM from oversized requests. (#268)
- Aggregate and change-aggregate batch endpoints now cap batches at 100 entries to prevent worker-pool exhaustion. (#269)
- Household impact jobs now persist the `baseline_job_id` on the reform job's JSON `request_data` column by replacing the dict rather than mutating it in place (SQLAlchemy doesn't track in-place JSON mutations). (#270)
- Household endpoints now validate entity values against variable dtypes (rejecting mixed-dtype inputs with 422) and pick dtype-compatible column defaults to prevent the simulation kernel from building object-dtype DataFrames. (#271)
- List endpoints (`/parameters`, `/parameter-values`, `/outputs/aggregates`, `/outputs/change-aggregates`) now enforce `limit <= 500` and reject non-positive values to prevent full-table scans. (#272)
- Agent sandbox now URL-encodes path parameters so values containing `/`, `#`, or `?` cannot escape the intended path segment. (#273)
- `download_dataset` now rejects path-traversal filepaths (`../../etc/passwd`, absolute paths) that would write outside the Modal dataset cache root. (#274)
- Replaced the deprecated `asyncio.get_event_loop()` call inside `/agent/run` with `asyncio.get_running_loop()`. (#275)
- Replaced deprecated `datetime.utcnow()` with timezone-aware `datetime.now(timezone.utc)` in the agent router. (#276)
- `settings.database_url` now raises `ValueError` for non-local Supabase URLs that lack `supabase_db_url` instead of silently synthesising a `postgres:postgres@...` string. (#277)


0.6.3 (2026-04-16)

# Fixed

- Stored `/households` definitions now use the same plural entity-list contract as household calculation, including validation for multi-group person/entity linkage and compatibility coercion for legacy singular payloads. (#256)


0.6.2 (2026-04-12)

# Changed

- Reject shared runtime bundle reuse when the compared database rows point at different model identities, even if their runtime version strings match. (runtime-version-resolution)


0.6.1 (2026-04-09)

# Fixed

- Moved api-v2 version routing to dedicated Modal registries so api-v2-alpha deployments no longer overwrite the legacy simulation API registry. (#215)


0.6.0 (2026-04-09)

# Added

- User-household associations can now be reassigned to a different `household_id` while preserving the existing association record. (household-association-reassignment)


0.5.3 (2026-04-09)

# Changed

- Update policyengine-us to 1.633.2. (policyengine-us-1.633.2)


0.5.2 (2026-04-09)

# Changed

- Update policyengine-us to 1.633.1. (policyengine-us-1.633.1)


0.5.1 (2026-04-08)

# Fixed

- Skip the deploy and integration-test pipeline for automated package version update commits. (#208)


0.5.0 (2026-04-06)

# Added

- Versioned Modal deployments: each deploy creates a named app (`policyengine-v2-us{X}-uk{Y}`) with exact country package version pins, allowing multiple versions to coexist. Cloud Run routes to the correct version via Modal Dict registries. (#201)

# Changed

- Refactored monolithic `modal_app.py` into `modal/` package with separate modules for app definition, images, shared utilities, and functions. (#201)

# Removed

- Deleted monolithic `modal_app.py` (3,450 lines), replaced by `modal/` package. (#201)


0.4.4 (2026-03-18)

# Fixed

- Versioning workflow now creates GitHub Releases by using App token to trigger Phase 2. (#149)


0.4.3 (2026-03-18)

# Fixed

- Auto-updater PRs now include a changelog fragment. (#147)


0.4.2 (2026-03-18)

# Fixed

- Use GitHub App token in country package auto-updater so PRs trigger CI tests. (#144)


0.4.1 (2026-03-17)

# Fixed

- Serialize lists and dicts as JSON in bulk_insert for Postgres COPY compatibility (fix-seed-json)


0.4.0 (2026-03-17)

# Added

- Automated GitHub Actions workflow to check for country package updates and open PRs. (#135)


0.3.4 (2026-03-16)

# Changed

- Support staging and production targets in db-reset workflow with environment-scoped secrets (#137)


0.3.3 (2026-03-16)

# Fixed

- Merge Alembic heads to resolve multiple head revisions blocking CI/CD migrations (#134)


0.3.2 (2026-03-16)

# Changed

- Split CI/CD database migrations into separate staging and production jobs with environment-scoped Supabase secrets (#133)


0.4.0 (2026-03-13)

# Added

- Standardize all endpoints on `country_id` instead of `tax_benefit_model_name` (#109)
- Default metadata endpoints (variables, parameters, datasets) to latest model version with optional version pinning (#109)
- Dual policy IDs (`baseline_policy_id` / `reform_policy_id`) on reports and `EXECUTION_DEFERRED` report status (#109)
- Auto-start `EXECUTION_DEFERRED` reports on GET endpoint access (#109)
- Convert VARCHAR enum columns to native PostgreSQL enums with `values_callable` (#109)


0.3.1 (2026-03-11)

# Fixed

- Add Alembic merge migration to resolve multiple head revisions from parallel feature branches (#129)


0.3.0 (2026-03-11)

# Added

- Add parameter_nodes table to store folder/category labels for parameter tree navigation (#124)


0.2.9 (2026-03-11)

# Fixed

- Enable follow_redirects in staging integration tests to handle FastAPI's trailing-slash 307 redirects. (fix-staging-tests-redirect)


0.2.8 (2026-03-11)

# Fixed

- Fix staging and canary URL extraction in deploy workflow — gcloud format filter returned empty, replaced with JSON + jq parsing. (fix-tagged-url-extraction)


0.2.7 (2026-03-11)

# Fixed

- Increase Cloud Run startup probe timeout to 40 seconds (was 15s) to prevent deployment failures with heavier policyengine imports. (increase-startup-probe)


0.2.6 (2026-03-11)

# Fixed

- Sync ANTHROPIC_API_KEY to Modal environments via deploy pipeline, fixing agent sandbox deploy failure. (sync-anthropic-key-modal)


0.2.5 (2026-03-10)

# Fixed

- Fix region seeding crash caused by unpacking 2 values from 3-tuple return of seed_us_regions and seed_uk_regions. (fix-seed-tuple-unpack)


0.2.4 (2026-03-10)

# Fixed

- Bump policyengine from 3.2.0 to 3.2.1, fixing missing `policyengine.countries` module needed for region seeding. (bump-policyengine-3.2.1)


0.2.3 (2026-03-10)

# Changed

- Rename SUPABASE_SERVICE_KEY to SUPABASE_SECRET_KEY across codebase, aligning with Supabase's new key naming. Add secret key to Terraform, deploy.yml, and Modal secrets sync. (rename-secret-key)


0.2.2 (2026-03-10)

# Fixed

- Update policyengine-uk from 2.45.4 to 2.75.1, fixing dataset seeding crash (sim.dataset[year] API change). (bump-uk-version)


0.2.1 (2026-03-10)

# Fixed

- Add missing --reset flag to db-reset workflow so init.py actually drops existing tables before recreating them. (db-reset-flag)


0.2.0 (2026-03-10)

# Added

- Add staging deployment pipeline with integration tests, canary deploys, and release automation. (staging-pipeline)

# Fixed

- Fix MODAL_ENVIRONMENT not being set in Terraform, causing production to use testing Modal environment. (modal-env-fix)
- Switch policyengine dependency from git branch to PyPI release (>=3.2.0). (policyengine-dep)

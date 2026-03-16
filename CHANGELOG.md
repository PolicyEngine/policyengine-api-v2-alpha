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

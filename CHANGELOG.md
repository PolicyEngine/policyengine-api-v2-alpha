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

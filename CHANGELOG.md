0.2.1 (2026-03-10)

# Fixed

- Add missing --reset flag to db-reset workflow so init.py actually drops existing tables before recreating them. (db-reset-flag)


0.2.0 (2026-03-10)

# Added

- Add staging deployment pipeline with integration tests, canary deploys, and release automation. (staging-pipeline)

# Fixed

- Fix MODAL_ENVIRONMENT not being set in Terraform, causing production to use testing Modal environment. (modal-env-fix)
- Switch policyengine dependency from git branch to PyPI release (>=3.2.0). (policyengine-dep)

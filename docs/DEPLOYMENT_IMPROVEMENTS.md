# Deployment Pipeline Improvements

Proposed improvements to `deploy.yml` and supporting infrastructure, ordered by priority.

## Current state

The deploy pipeline is a single monolithic GitHub Actions job:

```
push to main → test → migrate DB → build Docker → push image
             → terraform apply → update Cloud Run → sync Modal secrets
             → deploy Modal functions → validate Modal secrets
```

No rollback mechanism, no health checks, no canary deployment, no vulnerability scanning.

## P0: Fix Modal / Cloud Run deploy ordering

**Problem:** Cloud Run is updated (new API image) *before* Modal functions are deployed. During that window, the new API may call old Modal functions with incompatible signatures.

**Fix:** Deploy Modal functions before shifting Cloud Run traffic. Modal's deploy is zero-downtime — new containers build while old ones serve, then swap atomically. The old API continues calling old Modal functions during the Modal build. Once Modal is ready, update Cloud Run so the new API calls the new Modal functions.

```
migrate → build image → deploy Modal → update Cloud Run
```

## P0: Add terraform plan before apply

**Problem:** `terraform apply -auto-approve` applies whatever it computes at that instant. If state drifted or an unrelated change was introduced, the apply could make unexpected infrastructure changes.

**Fix:** Generate a saved plan, then apply exactly that plan:

```yaml
- name: Terraform plan
  working-directory: ./terraform
  run: terraform plan -out=tfplan -input=false

- name: Terraform apply
  working-directory: ./terraform
  run: terraform apply -input=false tfplan
```

Set `TF_IN_AUTOMATION=true` as an env var to suppress interactive hints.

## P1: Add health checks to Cloud Run

**Problem:** The Terraform Cloud Run definition has no startup or liveness probes. Cloud Run can route traffic to instances that aren't ready or have become unhealthy.

**Fix:** Add probes to the container definition in `terraform/main.tf`:

```hcl
startup_probe {
  http_get {
    path = "/health"
    port = 80
  }
  initial_delay_seconds = 0
  timeout_seconds       = 3
  period_seconds        = 3
  failure_threshold     = 5
}

liveness_probe {
  http_get {
    path = "/health"
    port = 80
  }
  initial_delay_seconds = 10
  timeout_seconds       = 3
  period_seconds        = 10
  failure_threshold     = 3
}
```

## P1: Add canary deployment with smoke test

**Problem:** `gcloud run services update` immediately shifts 100% of traffic to the new revision. If the new image is broken, all users are affected instantly.

**Fix:** Deploy with zero traffic, smoke-test the canary, then shift:

```yaml
- name: Deploy canary (no traffic)
  run: |
    gcloud run deploy ${{ vars.API_SERVICE_NAME }} \
      --region=${{ vars.GCP_REGION }} \
      --image=$IMAGE_URL:${{ github.sha }} \
      --tag=canary \
      --no-traffic

- name: Smoke test canary
  run: |
    CANARY_URL=$(gcloud run services describe ${{ vars.API_SERVICE_NAME }} \
      --region=${{ vars.GCP_REGION }} \
      --format='value(status.traffic[tag=canary].url)')
    curl -f "$CANARY_URL/health" || exit 1

- name: Shift traffic to new revision
  run: |
    gcloud run services update-traffic ${{ vars.API_SERVICE_NAME }} \
      --region=${{ vars.GCP_REGION }} \
      --to-latest
```

## P1: Split into separate jobs

**Problem:** Everything runs in one monolithic job. A failure at step N leaves steps 1..N-1 applied with no automated recovery. For example: Terraform succeeds but Modal deploy fails → new infrastructure config, old Modal functions.

**Fix:** Split into jobs with explicit dependencies:

```yaml
jobs:
  test:
    # Run unit tests

  migrate:
    needs: test
    # alembic upgrade head

  build:
    needs: test
    # Build and push Docker image (parallel with migrate)

  deploy-modal:
    needs: [migrate, build]
    # Deploy Modal functions + sync secrets

  deploy-cloudrun:
    needs: [deploy-modal, build]
    # Canary deploy + smoke test + traffic shift

  smoke-test:
    needs: deploy-cloudrun
    # End-to-end API validation

  rollback:
    needs: [deploy-modal, deploy-cloudrun, smoke-test]
    if: failure()
    # Revert Cloud Run traffic to previous revision
```

Key benefits:
- `migrate` and `build` run in parallel (saves ~2-3 min)
- Modal deploys before Cloud Run (fixes version skew)
- Failure at any stage stops downstream jobs
- Rollback job triggers automatically on failure

## P2: Move secrets to Google Secret Manager

**Problem:** Secrets live in three places: GitHub Actions secrets, Terraform variables (ending up in TF state in GCS), and Modal secrets. Rotating a secret requires re-running the full deploy pipeline.

**Fix:** Use Google Secret Manager as single source of truth. Cloud Run natively supports Secret Manager references:

```hcl
env {
  name = "SUPABASE_URL"
  value_source {
    secret_key_ref {
      secret  = "supabase-url"
      version = "latest"
    }
  }
}
```

This eliminates secrets from Terraform state and decouples secret rotation from deploys. Secrets are fetched at container start time.

For Modal, `modal secret create --force` in CI is the only option today. Add a scheduled weekly workflow to sync Modal secrets, ensuring convergence even if the main deploy doesn't run.

## P2: Add Docker image vulnerability scanning

**Problem:** Images are built and pushed without scanning for known CVEs.

**Fix:** Add a scan step between build and push:

```yaml
- name: Scan image for vulnerabilities
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE_URL }}:${{ github.sha }}
    format: 'table'
    exit-code: '1'
    severity: 'CRITICAL,HIGH'
    ignore-unfixed: true
```

## P3: Fix Dockerfile layer caching

**Problem:** `uv.lock` is not copied before `src/`, so dependency installs rebuild on every source change.

**Fix:**

```dockerfile
# Copy dependency files first (change rarely)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (cached unless lock file changes)
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system -e .

# Copy source code (changes frequently)
COPY src/ ./src/
```

## P3: Add automated rollback job

**Problem:** Recovery from a bad deploy is entirely manual.

**Fix:** Add a rollback job that triggers on failure:

```yaml
rollback:
  needs: [deploy-cloudrun, smoke-test]
  if: failure()
  steps:
    - name: Revert Cloud Run traffic
      run: |
        PREV_REVISION=$(gcloud run revisions list \
          --service=${{ vars.API_SERVICE_NAME }} \
          --region=${{ vars.GCP_REGION }} \
          --sort-by=~creationTimestamp \
          --format='value(metadata.name)' --limit=2 | tail -1)
        gcloud run services update-traffic ${{ vars.API_SERVICE_NAME }} \
          --region=${{ vars.GCP_REGION }} \
          --to-revisions=$PREV_REVISION=100
```

Note: Modal functions cannot be rolled back automatically. Ensure Modal function changes are backward-compatible.

## P3: Remove `:latest` tag confusion

**Problem:** `main.tf` references `:latest` in the image but uses `ignore_changes` on image, so Terraform never controls the running revision. The actual deploy happens via `gcloud run services update` with the SHA. This is confusing and could cause issues if someone runs Terraform outside the pipeline.

**Fix:** Either stop pushing `:latest` entirely, or change the Terraform image to a placeholder value that makes the `ignore_changes` intent explicit.

## P3: Add Terraform drift detection

**Problem:** Manual changes via GCP console diverge from Terraform-managed state with no detection.

**Fix:** Scheduled weekly workflow:

```yaml
name: Terraform Drift Detection
on:
  schedule:
    - cron: '0 8 * * 1'  # Monday 8am UTC
  workflow_dispatch:

jobs:
  drift-check:
    runs-on: ubuntu-latest
    steps:
      - name: Detect drift
        working-directory: ./terraform
        id: drift
        run: terraform plan -detailed-exitcode -input=false
        continue-on-error: true

      - name: Alert on drift
        if: steps.drift.outcome == 'failure'
        run: echo "::warning::Infrastructure drift detected"
```

`terraform plan -detailed-exitcode` returns exit code 2 when changes are detected.

## P3: Add Terraform plan on PRs

Show infrastructure changes in PR reviews before merge:

```yaml
# In test.yml or a separate workflow
- name: Terraform plan (PR check)
  if: github.event_name == 'pull_request'
  working-directory: ./terraform
  run: |
    terraform init -input=false
    terraform plan -input=false -no-color
```

Post the plan output as a PR comment so reviewers can see what infrastructure changes a code change implies.

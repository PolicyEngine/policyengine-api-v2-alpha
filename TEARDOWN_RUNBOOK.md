# API v2 alpha — deprecation & teardown runbook

Runbook for retiring the `policyengine-api-v2-alpha` service (the "reduced APIv2
middle ground" at `v2.api.policyengine.org`) and archiving this repo, now that
the frontend has been migrated off it.

**Status:** draft plan — nothing here has been executed. Steps are ordered;
run top to bottom.

## Context / preconditions

- The `policyengine-app-v2` frontend no longer depends on this service
  (PR PolicyEngine/policyengine-app-v2#1104, tracked by #1105 — merged). It now
  uses the v1 API exclusively.
- Live traffic to `v2.api.policyengine.org` is now essentially crawlers/bots
  (Bytespider, Amazonbot, bingbot, OAI-SearchBot, blank-UA scanners) plus a
  thinning tail of cached browser sessions that will decay as the merged
  frontend deploys and caches expire. No heavy production consumer remains.

## Scope decision — two things we deliberately keep **in situ** for now

To avoid blocking the teardown, this runbook does **targeted resource deletes,
not a GCP project shutdown**, and leaves these two things running:

1. **`gs://policyengine-uk-microdata`** (~20 GB) + its reader SA
   `pe-data-reader@`. This bucket lives in the `policyengine-api-v2-alpha` GCP
   project but is **not used by this app** (the app stores data in *Supabase*
   storage, not GCS). It is unrelated UK microdata, almost certainly owned by the
   data pipeline. Because it sits in this project, we do **not** delete the
   project. Re-homing it and deleting the project is a later pass.
2. **The Modal `agent-sandbox` app.** Left running (idle ≈ $0). Untangling the
   agent/MCP stack is a later pass.

> ⚠️ **Coupling to accept:** the `/mcp` and `/agent` **HTTP endpoints are served
> by the Cloud Run app** — deleting Cloud Run (Step 3) takes those endpoints
> offline. The Modal sandbox survives but nothing will trigger it. If live
> MCP/agent must be preserved, Cloud Run + Supabase have to stay up and there are
> no savings. This runbook assumes those HTTP endpoints going dark is acceptable.

## Owner legend

`[repo]` = actions in this GitHub repo · `[gcp]` = Google Cloud ·
`[dns]` = policyengine.org DNS provider (Cloudflare/registrar) ·
`[supabase]` = Supabase console · `[modal]` = Modal (needs a Modal token).

---

## Step 1 — Freeze CI `[repo]` (reversible)

Disable the workflows so nothing redeploys and the every-30-minutes
`update-country-packages` cron stops:

```bash
gh workflow disable deploy.yml                  --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable db-reset.yml                --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable update-country-packages.yml --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable versioning.yml              --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable test.yml                    --repo PolicyEngine/policyengine-api-v2-alpha
```

## Step 2 — Cut traffic `[gcp]` + `[dns]`

```bash
# 2a. [gcp] remove the Cloud Run custom domain mapping
gcloud beta run domain-mappings delete v2.api.policyengine.org \
  --region=us-central1 --project=policyengine-api-v2-alpha
```

```
# 2b. [dns] delete the `v2.api` CNAME record (currently -> ghs.googlehosted.com)
#     at the policyengine.org DNS provider.
```

Do 2b right after 2a so requests stop resolving cleanly (no 5xx window).

## Step 3 — Delete the Cloud Run compute `[gcp]` (irreversible)

Surgical `gcloud` deletes (not `terraform destroy`, to avoid needing the Supabase
TF vars and to leave the project healthy). This removes the always-on
instance — the dominant cost line.

```bash
gcloud run services delete policyengine-api-v2-alpha-api \
  --region=us-central1 --project=policyengine-api-v2-alpha --quiet

gcloud artifacts repositories delete policyengine-api-v2-alpha \
  --location=us-central1 --project=policyengine-api-v2-alpha --quiet

gcloud iam service-accounts delete \
  pe-api-v2-alpha-run@policyengine-api-v2-alpha.iam.gserviceaccount.com \
  --project=policyengine-api-v2-alpha --quiet
```

## Step 4 — Wind down the *sim* Modal apps; keep the sandbox `[modal]`

```bash
modal app list --env=main       # and: modal app list --env=staging
# stop the versioned policyengine-api-v2-alpha *simulation* app in BOTH envs
modal app stop <sim-app-name>   # main, then staging
```

- **Leave** the `agent-sandbox` app running.
- **Do not** delete the shared `main` / `staging` Modal environments —
  `policyengine-sim-api` also uses Modal.

## Step 5 — Supabase `[supabase]` (irreversible)

Confirm the staging + prod projects hold only seed/test data (they have user
tables and took live traffic, so verify). Export a snapshot if in any doubt,
then delete **both** Supabase projects.

## Step 6 — Retire the repo `[repo]`

```bash
gh secret list --repo PolicyEngine/policyengine-api-v2-alpha
# delete the Supabase / Modal / Logfire / Anthropic / HF / GCP-WIF secrets
gh secret delete <NAME> --repo PolicyEngine/policyengine-api-v2-alpha   # per secret
```

- Add a short README deprecation note pointing to the v1 API
  (`policyengine-api`) and `policyengine-sim-api`.
- Archive the repo (read-only; preserves history; disables Actions):

```bash
gh repo archive PolicyEngine/policyengine-api-v2-alpha
```

## Step 7 — Final GCP cleanup `[gcp]` (after Steps 1–3 confirmed)

```bash
gcloud iam service-accounts delete \
  github-deploy@policyengine-api-v2-alpha.iam.gserviceaccount.com \
  --project=policyengine-api-v2-alpha --quiet

gcloud storage rm --recursive gs://policyengine-api-v2-alpha-terraform   # TF state, no longer needed
```

**Leave** `gs://policyengine-uk-microdata`, `pe-data-reader@`, and the project.

---

## Result

**Removed:** Cloud Run (always-on cost), Artifact Registry repo, Terraform state
bucket, deploy + runtime service accounts, custom domain mapping + DNS, both
Supabase projects, the sim Modal apps, and all CI. Repo archived.

**Left in situ (deferred):** the GCP project shell, `gs://policyengine-uk-microdata`
(+ `pe-data-reader@`), and the Modal `agent-sandbox` app.

**Cost recovered:** Cloud Run (~$25–40/mo) + Supabase (up to ~$25/mo per
project). Residual ≈ $0.40/mo for the 20 GB of microdata storage that's being
kept anyway.

## Deferred to a later pass

- Re-home `gs://policyengine-uk-microdata` to its proper project, then delete the
  `policyengine-api-v2-alpha` GCP project entirely for zero residual cost.
- Decide the agent/MCP's fate (revive elsewhere, or delete the Modal
  `agent-sandbox` app and remove the MCP/agent docs).

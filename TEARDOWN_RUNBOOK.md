# API v2 alpha — deprecation & teardown runbook

Runbook for retiring the `policyengine-api-v2-alpha` service (the "reduced APIv2
middle ground" at `v2.api.policyengine.org`) and archiving this repo, now that
the frontend has been migrated off it.

**Status:** _mostly complete._ Steps 1–3 executed; Step 4 skipped; Step 5 nearly
done (staging DB deleted, production DB backed up + pending its final delete);
the AWS/ECS check was skipped (no AWS access); **Step 6 done — repo archived**
(secret deletion + README note intentionally skipped); Step 7 (GCP SA + TF state
bucket) still pending. Per-step status is marked inline below.

### Execution status at a glance

| Step | What | Status |
| --- | --- | --- |
| 1 | Freeze CI | ✅ done (all **6** workflows disabled) |
| 2 | Cut traffic (domain mapping + DNS) | ✅ done |
| 3 | Delete Cloud Run compute | ✅ done |
| 4 | Wind down sim Modal apps | ⏭️ **skipped** (owner decision) |
| 5 | Supabase | 🔄 staging deleted; prod backed up, **pending final delete** |
| — | AWS/ECS leftovers | ⏭️ **skipped** — no AWS access (names recorded for later) |
| 6 | Retire the repo | 🔻 **archived**; secret deletion + README note intentionally skipped |
| 7 | Final GCP cleanup (SA + TF state bucket) | ⏳ pending |

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
   project but is **not used by this app** (the app stored data in *Supabase*
   storage, not GCS). It is unrelated UK microdata, almost certainly owned by the
   data pipeline. Because it sits in this project, we do **not** delete the
   project. Re-homing it and deleting the project is a later pass.
2. **The Modal `policyengine-sandbox` (agent) app.** Left running (idle ≈ $0).
   Untangling the agent/MCP stack is a later pass.

> ⚠️ **Coupling to accept:** the `/mcp` and `/agent` **HTTP endpoints are served
> by the Cloud Run app** — deleting Cloud Run (Step 3) takes those endpoints
> offline. The Modal sandbox survives but nothing will trigger it. If live
> MCP/agent must be preserved, Cloud Run + Supabase have to stay up and there are
> no savings. This runbook assumes those HTTP endpoints going dark is acceptable.

## Owner legend

`[repo]` = actions in this GitHub repo · `[gcp]` = Google Cloud ·
`[dns]` = policyengine.org DNS provider (Cloudflare/registrar) ·
`[supabase]` = Supabase console · `[modal]` = Modal (needs a Modal token) ·
`[aws]` = AWS console (needs AWS creds).

---

## Step 1 — Freeze CI `[repo]` (reversible) — ✅ DONE

Disable the workflows so nothing redeploys and the every-30-minutes
`update-country-packages` cron stops. **Note:** there were **6** workflows, not 5
— a `Reseed database` workflow (id `276042767`) only surfaced via
`gh workflow list --all` and was also disabled.

```bash
gh workflow disable deploy.yml                  --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable db-reset.yml                --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable update-country-packages.yml --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable versioning.yml              --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable test.yml                    --repo PolicyEngine/policyengine-api-v2-alpha
gh workflow disable 276042767                   --repo PolicyEngine/policyengine-api-v2-alpha  # "Reseed database"
```

## Step 2 — Cut traffic `[gcp]` + `[dns]` — ✅ DONE

```bash
# 2a. [gcp] remove the Cloud Run custom domain mapping
#     NB: the domain is a flag (--domain=…), not a positional arg.
gcloud beta run domain-mappings delete \
  --domain=v2.api.policyengine.org \
  --region=us-central1 --project=policyengine-api-v2-alpha
```

```
# 2b. [dns] delete the `v2.api` CNAME record (was -> ghs.googlehosted.com)
#     at the policyengine.org DNS provider.  (Done by owner.)
```

## Step 3 — Delete the Cloud Run compute `[gcp]` (irreversible) — ✅ DONE

Surgical `gcloud` deletes (not `terraform destroy`, to avoid needing the Supabase
TF vars and to leave the project healthy). This removed the always-on
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

## Step 4 — Wind down the *sim* Modal apps; keep the sandbox `[modal]` — ⏭️ SKIPPED

**Skipped by owner decision** (risk of touching production sim-api apps without
live Modal access to verify). The alpha's sim apps are name-distinct from the
`policyengine-sim-api` production apps (`policyengine-simulation-*`), but this was
not exercised. If revisited later:

```bash
modal app list --env=main       # and: modal app list --env=staging
# stop the versioned alpha *simulation* app (policyengine-v2-us*-uk*) in BOTH envs
modal app stop <sim-app-name>   # main, then staging
```

- **Leave** the `policyengine-sandbox` (agent) app running.
- **Do not** delete the shared `main` / `staging` Modal environments —
  `policyengine-sim-api` also uses Modal.

## Step 5 — Supabase `[supabase]` (irreversible) — 🔄 IN PROGRESS

There were **two** Supabase projects (both in org `jygirqnhxzbevhozzrzi`), wired
via env-scoped GitHub secrets (`staging` + `production` environments each carry
their own `SUPABASE_URL` / `SUPABASE_DB_URL`). Confirmed via `psql` that both hold
the alpha's own schema (alembic rev `fb663a6e28e4`) and **no** other service's
tables. `policyengine-sim-api` does **not** use Supabase at all, so nothing else
depends on these DBs.

| Env | Project name | Ref | Region | Verified contents | State |
| --- | --- | --- | --- | --- | --- |
| staging | `api-v2-testing` | `orbsyilijkbatfmahnyu` | us-east-1 | 0 users; ~36 households / 182 policies of test data; rest = reproducible seed | ✅ **deleted** |
| production | `api-v2-alpha` | `zoogijcmzdgpqfxwdxca` | eu-west-1 | `auth.users`=0 & `public.users`=0 (no real accounts); 23 households / 263 policies / 2 reports of anonymous content; rest = reproducible seed | 💾 backed up, **pending delete** |

**Connection gotcha (for anyone re-running this):** the direct
`db.<ref>.supabase.co` host is **IPv6-only** (no A record) and won't resolve on a
v4-only network. Use the **session pooler** instead:
`postgresql://postgres.<ref>:<pw>@aws-1-<region>.pooler.supabase.com:5432/postgres`.
`supabase db dump` additionally requires Docker (it runs a versioned
`supabase/postgres:17.x` pg_dump container) — the server is **Postgres 17**, so a
local pg_dump 15 is refused.

**Production backup taken** (local, outside any git repo):
`/Users/administrator/Documents/PolicyEngine/api-v2-alpha-prod-backup-20260709/`
- `roles.sql` (297 B), `schema.sql` (42 KB, 33 tables),
  `data.sql` (170 MB, `--use-copy --data-only`). Per-table COPY row counts were
  verified against the live DB — faithful capture.
- **Not** in the SQL dump: the storage bucket blobs. The `datasets` bucket holds
  **15 `.h5` files, 866 MB** (enhanced FRS/CPS + base FRS microdata, projected per
  year). These are standard, reproducible PolicyEngine datasets (also on the
  Hugging Face Hub) — deliberately **not** backed up.

**Remaining action:** delete the `api-v2-alpha` project in the Supabase dashboard
(Settings → General → Delete project) — this also drops the `datasets` storage
bucket. Then Step 5 is complete.

## AWS/ECS leftovers `[aws]` — ⚠️ NEW, needs investigation

Discovered during Step 5: the repo still carries **AWS/ECS** config that predates
the GCP move (repo vars dated 2025-11-21, before the GCP vars on 2025-12-09),
suggesting the service first ran on **AWS ECS/Fargate** then migrated to GCP Cloud
Run. Relevant repo settings:

- vars: `AWS_REGION=us-east-1`, `ECR_REPOSITORY_NAME=policyengine-api-v2-alpha`,
  `ECS_CLUSTER_NAME=policyengine-api-v2-alpha-cluster`,
  `ECS_API_SERVICE_NAME=policyengine-api-v2-alpha-api`,
  `ECS_WORKER_SERVICE_NAME=policyengine-api-v2-alpha-worker`
- secret: `AWS_ROLE_ARN`

**Action:** in the AWS account (us-east-1), check for a live ECS cluster/service
(Fargate tasks = ongoing cost) and the ECR repo; delete if orphaned. Needs AWS
creds/console.

> ⏭️ **Not performed** — owner has no AWS access. The resource names are recorded
> above so whoever holds the AWS account can check later. They were captured here
> before archiving because the repo settings were the only breadcrumb to them.

## Step 6 — Retire the repo `[repo]` — 🔻 ARCHIVED

**What was done:** the repo was archived (`gh repo archive`), making it read-only,
disabling Actions, and preserving history + all branches (including this one).

**Intentionally skipped (owner decision):**
- **Secret deletion** — left in place. The Supabase secrets are already dead (both
  projects deleted). The still-live ones (`MODAL_TOKEN_*`, `HUGGING_FACE_TOKEN`,
  `AWS_ROLE_ARN`, GCP WIF) remain; Actions is disabled by the archive, so they
  can't be exercised from here. Delete them later if you want full hygiene
  (requires temporarily un-archiving, since archived repos are read-only).
- **README deprecation note** — skipped; GitHub's "Public archive" banner already
  signals deprecation.

The original plan (for reference) was:

```bash
gh secret list --repo PolicyEngine/policyengine-api-v2-alpha
# delete the Supabase / Modal / Logfire / HF / AWS / GCP-WIF secrets, e.g.:
#   SUPABASE_URL, SUPABASE_KEY, SUPABASE_SECRET_KEY, SUPABASE_DB_URL,
#   SUPABASE_POOLER_URL, MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, LOGFIRE_TOKEN,
#   HUGGING_FACE_TOKEN, AWS_ROLE_ARN  (plus the staging/production env secrets)
gh secret delete <NAME> --repo PolicyEngine/policyengine-api-v2-alpha   # per secret
```

- Add a short README deprecation note pointing to the v1 API
  (`policyengine-api`) and `policyengine-sim-api`.
- Archive the repo (read-only; preserves history; disables Actions):

```bash
gh repo archive PolicyEngine/policyengine-api-v2-alpha
```

## Step 7 — Final GCP cleanup `[gcp]` (after Steps 1–3 confirmed) — ⏳ PENDING

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
Supabase projects, and all CI. Repo archived. (Sim Modal apps intentionally left —
Step 4 skipped.)

**Left in situ (deferred):** the GCP project shell, `gs://policyengine-uk-microdata`
(+ `pe-data-reader@`), the Modal `policyengine-sandbox` (agent) app, and the
alpha's sim Modal apps.

**Cost recovered:** Cloud Run (~$25–40/mo) + Supabase (up to ~$25/mo per
project). Residual ≈ $0.40/mo for the 20 GB of microdata storage that's being
kept anyway. (Any live AWS ECS/Fargate found above would be additional savings.)

## Deferred to a later pass

- Re-home `gs://policyengine-uk-microdata` to its proper project, then delete the
  `policyengine-api-v2-alpha` GCP project entirely for zero residual cost.
- Decide the agent/MCP's fate (revive elsewhere, or delete the Modal
  `policyengine-sandbox` app and remove the MCP/agent docs).
- Wind down the alpha's sim Modal apps (Step 4, skipped for now).

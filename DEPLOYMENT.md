# AWS deployment guide

## Prerequisites

1. AWS account with appropriate permissions
2. AWS CLI installed and configured
3. Supabase project set up
4. Redis instance (recommend Upstash for serverless Redis)
5. GitHub repository (PolicyEngine/policyengine-api-v2-alpha)

## Step 1: Create Terraform state bucket

The S3 bucket stores Terraform state and enables automated deployments:

```bash
make create-state-bucket
```

This creates `policyengine-api-v2-terraform-state` with versioning enabled.

**Note**: Only needs to be done once.

## Step 2: Set up GitHub OIDC and IAM role

1. Get your AWS account ID:

```bash
aws sts get-caller-identity --query Account --output text
```

2. Create OIDC provider (if not already done):

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
```

3. Create IAM role with required permissions:

**Option A: AWS Console**
   - AWS Console → IAM → Roles → Create role
   - Trusted entity type: Web identity
   - Identity provider: `token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
   - GitHub organization: `PolicyEngine`
   - GitHub repository: `policyengine-api-v2-alpha`
   - Name: `GitHubActionsDeployRole`
   - Attach policies: `AmazonECS_FullAccess`, `AmazonElastiCacheFullAccess`, `ElasticLoadBalancingFullAccess`, `AmazonEC2FullAccess`, `CloudWatchLogsFullAccess`

**Option B: AWS CLI (if updating existing role)**
```bash
./scripts/fix-iam-permissions.sh
```

4. Copy the role ARN: `arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActionsDeployRole`

## Step 3: Configure GitHub secrets and variables

Go to repo Settings → Secrets and variables → Actions

**Add these secrets** (Secrets tab):

```
AWS_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActionsDeployRole
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_DB_URL=postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
REDIS_URL=redis://default:[password]@your-redis.upstash.io:6379
LOGFIRE_TOKEN=pylf_v1_us_...
```

**Add these variables** (Variables tab):

```
AWS_REGION=us-east-1
ECR_REPOSITORY_NAME=policyengine-api-v2-alpha
ECS_CLUSTER_NAME=policyengine-api-v2-cluster
ECS_API_SERVICE_NAME=policyengine-api-v2-api
ECS_WORKER_SERVICE_NAME=policyengine-api-v2-worker
```

## Step 4: Deploy

Push to the main branch:

```bash
git checkout main
git push origin main
```

GitHub Actions will automatically:
1. Set up Terraform
2. Run `terraform init`
3. Run `terraform plan`
4. Run `terraform apply` (creates all infrastructure)
5. Build Docker image
6. Push to ECR
7. Update ECS services
8. Wait for deployment to stabilise

**First deployment**: Takes ~10 minutes as it creates VPC, load balancer, ECS cluster, etc.

**Subsequent deployments**: ~3-5 minutes (only updates Docker images and ECS tasks)

## Step 5: Verify deployment

After deployment completes:

1. **Get API endpoint**:
   ```bash
   cd terraform
   terraform output load_balancer_url
   ```

2. **Check health**:
   ```bash
   curl http://YOUR-ALB-URL/health
   ```

3. **View logs**:
   - AWS Console → CloudWatch → Log groups → `/ecs/policyengine-api-v2`

4. **Monitor services**:
   - AWS Console → ECS → Clusters → policyengine-api-v2-cluster

## Local deployment (optional)

Deploy infrastructure manually from your machine:

```bash
make deploy-local
```

This runs Terraform with variables from your `.env` file and prompts for confirmation before applying.

## Monitoring

- **Logs**: CloudWatch → `/ecs/policyengine-api-v2`
- **Services**: ECS → policyengine-api-v2-cluster
- **Metrics**: CloudWatch → ECS metrics
- **Logfire**: https://logfire-us.pydantic.dev/nikhilwoodruff/api-v2

## Updating the deployment

Any push to `main` automatically:
1. Updates infrastructure if Terraform files changed
2. Builds new Docker image
3. Deploys to ECS

## Cost estimates (us-east-1)

- VPC/networking: Free
- Application Load Balancer: ~€14/month
- ECS Fargate API (0.5 vCPU, 1GB): ~€13/month
- ECS Fargate Worker (1 vCPU, 2GB): ~€26/month
- CloudWatch Logs: ~€1/month
- S3 (Terraform state): ~€0.10/month
- Data transfer: Variable

**Total: ~€54/month** (plus data transfer and Redis costs)

## Troubleshooting

### Account doesn't support creating load balancers

If you see "This AWS account currently does not support creating load balancers":

1. Open AWS Support Center
2. Create case: Service limit increase
3. Select: Elastic Load Balancing
4. Request: Enable Application Load Balancer creation
5. Explain: Need ALB for ECS deployment

This typically takes 24-48 hours for new AWS accounts. Alternatively, check your account has valid payment method and is in good standing.

### GitHub Actions can't assume role

Trust policy must match your repo exactly:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:PolicyEngine/policyengine-api-v2-alpha:*"
        }
      }
    }
  ]
}
```

**Note**: `PolicyEngine` is case-sensitive (capital P and E)

### Terraform state locking errors

If deployment fails midway, you might see "state is locked". Wait 2 minutes for the lock to expire, or manually unlock:

```bash
# DON'T run this unless you're sure no other process is running Terraform
aws s3 rm s3://policyengine-api-v2-terraform-state/.terraform.tflock
```

### ECS tasks not starting

Check CloudWatch logs for errors. Common issues:
- Environment variables not set in GitHub secrets
- Supabase/Redis connection issues
- Image build failures

### High costs

Reduce task resources in `terraform/variables.tf`:
```hcl
api_cpu            = "256"   # Lower from 512
api_memory         = "512"   # Lower from 1024
worker_desired_count = 0      # Disable worker when not needed
```

Then push to trigger redeployment.

## Destroying infrastructure

To tear everything down:

```bash
cd terraform
./deploy.sh destroy
```

**Warning**: This deletes all resources and data. The Terraform state bucket is preserved for recovery.

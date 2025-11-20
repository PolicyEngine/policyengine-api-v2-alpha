# AWS deployment guide

## Prerequisites

1. AWS account with appropriate permissions
2. Terraform installed locally
3. Supabase project set up
4. Redis instance (recommend Upstash for serverless Redis)
5. GitHub repository with the main branch

## Step 1: Set up AWS credentials for Terraform

Install and configure AWS CLI with SSO (no long-term keys):

```bash
aws configure sso
```

Follow the prompts to authenticate via your browser.

## Step 2: Deploy infrastructure with Terraform

1. Create `terraform/terraform.tfvars`:

```hcl
aws_region         = "us-east-1"
project_name       = "policyengine-api-v2-alpha"
supabase_url       = "https://your-project.supabase.co"
supabase_key       = "your-anon-key"
supabase_db_url    = "postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres"
redis_url          = "redis://default:[password]@your-redis.upstash.io:6379"
logfire_token      = "pylf_v1_us_..."
storage_bucket     = "datasets"
api_cpu            = "512"
api_memory         = "1024"
api_desired_count  = 1
worker_cpu         = "1024"
worker_memory      = "2048"
worker_desired_count = 1
```

2. Deploy:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

3. Save the outputs:

```bash
terraform output
```

You'll get:
- `ecr_repository_url` - where to push Docker images
- `load_balancer_url` - your API endpoint
- `ecs_cluster_name` - cluster name for GitHub Actions
- `api_service_name` - API service name
- `worker_service_name` - worker service name

## Step 3: Set up GitHub OIDC (no access keys needed)

1. Get your AWS account ID:

```bash
aws sts get-caller-identity --query Account --output text
```

2. In AWS Console, go to IAM → Identity providers → Add provider:
   - Provider type: OpenID Connect
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
   - Click "Add provider"

3. Create IAM role for GitHub Actions:
   - IAM → Roles → Create role
   - Trusted entity type: Web identity
   - Identity provider: `token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
   - GitHub organization: your-username-or-org
   - GitHub repository: `policyengine-api-v2-alpha`
   - GitHub branch: `main`
   - Click Next

4. Attach these policies:
   - `AmazonECS_FullAccess`
   - `AmazonEC2ContainerRegistryPowerUser`

5. Name the role: `GitHubActionsDeployRole`

6. After creation, copy the role ARN (looks like `arn:aws:iam::123456789012:role/GitHubActionsDeployRole`)

## Step 4: Configure GitHub secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

```
AWS_REGION=us-east-1
AWS_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActionsDeployRole
ECR_REPOSITORY_NAME=policyengine-api-v2-alpha
ECS_CLUSTER_NAME=policyengine-api-v2-cluster
ECS_API_SERVICE_NAME=policyengine-api-v2-api
ECS_WORKER_SERVICE_NAME=policyengine-api-v2-worker
```

## Step 5: Deploy from GitHub

Push to the main branch:

```bash
git checkout main
git push origin main
```

GitHub Actions will automatically:
1. Build the Docker image
2. Push to ECR
3. Update ECS services
4. Wait for deployment to stabilise

**Note**: After running Terraform, the ECS services will initially fail to start (no Docker image exists yet). Once you push to `main` and GitHub Actions completes, the services will automatically recover and start successfully.

## Monitoring

- View logs: AWS Console → CloudWatch → Log groups → `/ecs/policyengine-api-v2`
- View services: AWS Console → ECS → Clusters → policyengine-api-v2-cluster
- API endpoint: Check Terraform output for `load_balancer_url`

## Updating the deployment

Any push to the `main` branch will trigger a new deployment automatically.

## Cost estimates (us-east-1)

- VPC/networking: Free (within free tier)
- Application Load Balancer: ~$16/month
- ECS Fargate API (0.5 vCPU, 1GB): ~$15/month
- ECS Fargate Worker (1 vCPU, 2GB): ~$30/month
- CloudWatch Logs: ~$1/month
- Data transfer: Variable

**Total: ~$62/month** (plus data transfer and Redis costs)

## Troubleshooting

### GitHub Actions can't assume role

Check the trust policy on your IAM role includes:
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
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/policyengine-api-v2-alpha:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### ECS tasks not starting

Check CloudWatch logs for errors. Common issues:
- Environment variables not set correctly
- Supabase/Redis connection issues
- Image build failures

### Deployment timeout

Increase health check grace period in task definition if app takes long to start.

### High costs

- Reduce task CPU/memory in `terraform.tfvars`
- Set `api_desired_count = 0` and `worker_desired_count = 0` when not in use
- Use AWS Cost Explorer to identify expensive resources

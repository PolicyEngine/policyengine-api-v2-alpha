# GitHub Actions OIDC provider
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# IAM role for GitHub Actions
resource "aws_iam_role" "github_actions" {
  name = "GitHubActionsDeployRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:PolicyEngine/policyengine-api-v2-alpha:*"
          }
        }
      }
    ]
  })

  tags = {
    Name = "GitHubActionsDeployRole"
  }
}

# Custom policy for GitHub Actions with all required permissions
resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "GitHubActionsDeployPolicy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          # ECR permissions
          "ecr:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # ECS permissions
          "ecs:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # ElastiCache permissions
          "elasticache:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # Load Balancer permissions
          "elasticloadbalancing:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # VPC and networking permissions
          "ec2:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # CloudWatch Logs permissions
          "logs:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # IAM permissions (for creating roles)
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:TagRole",
          "iam:PassRole",
          "iam:ListAttachedRolePolicies",
          "iam:ListRolePolicies",
          "iam:GetPolicyVersion",
          "iam:GetPolicy",
          "iam:ListPolicyVersions"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # S3 permissions for Terraform state
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning"
        ]
        Resource = [
          "arn:aws:s3:::policyengine-api-v2-terraform-state",
          "arn:aws:s3:::policyengine-api-v2-terraform-state/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          # DynamoDB for Terraform state locking
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:DescribeTable",
          "dynamodb:CreateTable"
        ]
        Resource = "arn:aws:dynamodb:*:*:table/terraform-state-lock"
      }
    ]
  })
}

# Output the role ARN for reference
output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role"
  value       = aws_iam_role.github_actions.arn
}

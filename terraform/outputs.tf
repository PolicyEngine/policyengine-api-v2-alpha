output "ecr_repository_url" {
  description = "ECR repository URL for Docker images"
  value       = aws_ecr_repository.api.repository_url
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

# output "load_balancer_url" {
#   description = "Load balancer URL for API"
#   value       = "http://${aws_lb.main.dns_name}"
# }
#
# Note: Without ALB, you'll need to get the task's public IP manually:
# aws ecs list-tasks --cluster <cluster_name> --service-name <api_service_name>
# aws ecs describe-tasks --cluster <cluster_name> --tasks <task_arn>

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "api_service_name" {
  description = "ECS API service name"
  value       = aws_ecs_service.api.name
}

output "worker_service_name" {
  description = "ECS worker service name"
  value       = aws_ecs_service.worker.name
}

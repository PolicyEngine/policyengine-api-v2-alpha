output "artifact_registry_url" {
  description = "Artifact Registry repository URL for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "redis_host" {
  description = "Redis host address"
  value       = google_redis_instance.redis.host
}

output "redis_port" {
  description = "Redis port"
  value       = google_redis_instance.redis.port
}

output "api_url" {
  description = "API service URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "worker_service_name" {
  description = "Worker service name"
  value       = google_cloud_run_v2_service.worker.name
}

output "api_service_name" {
  description = "API service name"
  value       = google_cloud_run_v2_service.api.name
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "policyengine-api-v2-alpha"
}

variable "region" {
  description = "GCP region for deployment"
  type        = string
  default     = "us-central1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "policyengine-api-v2-alpha"
}

variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  sensitive   = true
}

variable "supabase_key" {
  description = "Supabase anon/service key"
  type        = string
  sensitive   = true
}

variable "supabase_db_url" {
  description = "Supabase PostgreSQL connection URL"
  type        = string
  sensitive   = true
}

variable "logfire_token" {
  description = "Logfire observability token"
  type        = string
  sensitive   = true
}

variable "logfire_environment" {
  description = "Logfire environment (local, staging, prod)"
  type        = string
  default     = "prod"
}

variable "storage_bucket" {
  description = "GCS bucket name for datasets"
  type        = string
  default     = "datasets"
}

variable "api_cpu" {
  description = "CPU for API service (e.g., '1', '2')"
  type        = string
  default     = "1"
}

variable "api_memory" {
  description = "Memory for API service (e.g., '512Mi', '1Gi')"
  type        = string
  default     = "1Gi"
}

variable "api_min_instances" {
  description = "Minimum number of API instances"
  type        = number
  default     = 1
}

variable "api_max_instances" {
  description = "Maximum number of API instances"
  type        = number
  default     = 10
}

variable "worker_cpu" {
  description = "CPU for worker service"
  type        = string
  default     = "2"
}

variable "worker_memory" {
  description = "Memory for worker service"
  type        = string
  default     = "2Gi"
}

variable "worker_min_instances" {
  description = "Minimum number of worker instances"
  type        = number
  default     = 1
}

variable "worker_max_instances" {
  description = "Maximum number of worker instances"
  type        = number
  default     = 5
}

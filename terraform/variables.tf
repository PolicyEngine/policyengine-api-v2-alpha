variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
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

variable "storage_bucket" {
  description = "S3 bucket name for datasets"
  type        = string
  default     = "datasets"
}

variable "api_cpu" {
  description = "CPU units for API task (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "512"
}

variable "api_memory" {
  description = "Memory for API task in MB"
  type        = string
  default     = "1024"
}

variable "api_desired_count" {
  description = "Number of API tasks to run"
  type        = number
  default     = 1
}

variable "worker_cpu" {
  description = "CPU units for worker task"
  type        = string
  default     = "1024"
}

variable "worker_memory" {
  description = "Memory for worker task in MB"
  type        = string
  default     = "2048"
}

variable "worker_desired_count" {
  description = "Number of worker tasks to run"
  type        = number
  default     = 1
}

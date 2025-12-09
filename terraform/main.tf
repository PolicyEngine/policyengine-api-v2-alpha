terraform {
  required_version = ">= 1.0"

  backend "gcs" {
    bucket = "policyengine-api-v2-alpha-terraform"
    prefix = "terraform/state"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "redis.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# VPC for private services
resource "google_compute_network" "vpc" {
  name                    = "${var.project_name}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.project_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

# VPC connector for Cloud Run to access Redis
resource "google_vpc_access_connector" "connector" {
  name          = "${var.project_name}-connector"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"
  depends_on    = [google_project_service.required_apis]
}

# Redis instance using Cloud Memorystore
resource "google_redis_instance" "redis" {
  name               = "${var.project_name}-redis"
  tier               = "BASIC"
  memory_size_gb     = 1
  region             = var.region
  redis_version      = "REDIS_7_0"
  display_name       = "${var.project_name} Redis"
  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  depends_on = [google_project_service.required_apis]
}

# Artifact Registry repository for Docker images
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.project_name
  description   = "Docker repository for ${var.project_name}"
  format        = "DOCKER"

  depends_on = [google_project_service.required_apis]
}

# Service account for Cloud Run services
resource "google_service_account" "cloudrun" {
  account_id   = "${var.project_name}-cloudrun"
  display_name = "Cloud Run Service Account"
}

# Cloud Run service for API
resource "google_cloud_run_v2_service" "api" {
  name     = "${var.project_name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloudrun.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.project_name}:latest"

      resources {
        limits = {
          cpu    = var.api_cpu
          memory = var.api_memory
        }
      }

      ports {
        container_port = 80
      }

      env {
        name  = "SUPABASE_URL"
        value = var.supabase_url
      }
      env {
        name  = "SUPABASE_KEY"
        value = var.supabase_key
      }
      env {
        name  = "SUPABASE_DB_URL"
        value = var.supabase_db_url
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/0"
      }
      env {
        name  = "CELERY_BROKER_URL"
        value = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/0"
      }
      env {
        name  = "CELERY_RESULT_BACKEND"
        value = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/1"
      }
      env {
        name  = "LOGFIRE_TOKEN"
        value = var.logfire_token
      }
      env {
        name  = "LOGFIRE_ENVIRONMENT"
        value = var.logfire_environment
      }
      env {
        name  = "STORAGE_BUCKET"
        value = var.storage_bucket
      }
      env {
        name  = "API_PORT"
        value = "80"
      }
      env {
        name  = "DEBUG"
        value = "false"
      }
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_vpc_access_connector.connector,
    google_redis_instance.redis
  ]
}

# Cloud Run service for worker
resource "google_cloud_run_v2_service" "worker" {
  name     = "${var.project_name}-worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.cloudrun.email

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = var.worker_min_instances
      max_instance_count = var.worker_max_instances
    }

    containers {
      image   = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.project_name}:latest"
      command = ["celery"]
      args    = ["-A", "policyengine_api.tasks.celery_app", "worker", "--loglevel=info"]

      resources {
        limits = {
          cpu    = var.worker_cpu
          memory = var.worker_memory
        }
      }

      env {
        name  = "SUPABASE_URL"
        value = var.supabase_url
      }
      env {
        name  = "SUPABASE_KEY"
        value = var.supabase_key
      }
      env {
        name  = "SUPABASE_DB_URL"
        value = var.supabase_db_url
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/0"
      }
      env {
        name  = "CELERY_BROKER_URL"
        value = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/0"
      }
      env {
        name  = "CELERY_RESULT_BACKEND"
        value = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/1"
      }
      env {
        name  = "LOGFIRE_TOKEN"
        value = var.logfire_token
      }
      env {
        name  = "STORAGE_BUCKET"
        value = var.storage_bucket
      }
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_vpc_access_connector.connector,
    google_redis_instance.redis
  ]
}

# Allow public access to API
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

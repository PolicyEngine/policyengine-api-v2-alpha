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
    "artifactregistry.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
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
  account_id   = "pe-api-v2-alpha-run"
  display_name = "Cloud Run Service Account"
}

# Cloud Run service for API
resource "google_cloud_run_v2_service" "api" {
  name     = "${var.project_name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloudrun.email

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

  depends_on = [google_project_service.required_apis]

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# Cloud Run job for worker (polling-based, no port needed)
resource "google_cloud_run_v2_job" "worker" {
  name     = "${var.project_name}-worker"
  location = var.region

  template {
    template {
      service_account = google_service_account.cloudrun.email

      containers {
        image   = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.project_name}:latest"
        command = ["python", "-m", "policyengine_api.tasks.worker"]

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
          name  = "WORKER_POLL_INTERVAL"
          value = "60"
        }
      }

      timeout = "3600s"
      max_retries = 0
    }
  }

  depends_on = [google_project_service.required_apis]

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}

# Allow public access to API
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Custom domain mapping managed manually via gcloud CLI
# (Terraform domain mapping requires domain verification with service account)

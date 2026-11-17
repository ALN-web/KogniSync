# KogniSync on Google Cloud (asia-south1):
#   Cloud Run (API) -> Direct VPC egress -> Cloud SQL Postgres (private IP) + Memorystore Redis
#   Secret Manager for keys, Artifact Registry for images.
# The web app is served by Firebase Hosting, which rewrites /api/** to the Cloud Run service.

locals {
  name = "kognisync"
  apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudbuild.googleapis.com",
    "generativelanguage.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------------- Network ----------------

resource "google_compute_network" "vpc" {
  name                    = "${local.name}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "run" {
  name          = "${local.name}-run"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = "10.10.0.0/24"
}

# Private services access: Cloud SQL and Memorystore get private IPs in this range.
resource "google_compute_global_address" "private_services" {
  name          = "${local.name}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

# ---------------- Cloud SQL (Postgres) ----------------

resource "google_sql_database_instance" "pg" {
  name             = "${local.name}-pg"
  database_version = "POSTGRES_16"
  region           = var.region
  depends_on       = [google_service_networking_connection.private]

  settings {
    tier              = var.db_tier
    availability_type = var.db_high_availability ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    insights_config {
      query_insights_enabled = true
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "app" {
  name     = local.name
  instance = google_sql_database_instance.pg.name
}

resource "random_password" "db" {
  length  = 32
  special = false # keeps the connection URL free of characters that need escaping
}

resource "google_sql_user" "app" {
  name     = local.name
  instance = google_sql_database_instance.pg.name
  password = random_password.db.result
}

# ---------------- Memorystore (Redis) ----------------

resource "google_redis_instance" "cache" {
  name               = "${local.name}-redis"
  region             = var.region
  tier               = var.redis_tier
  memory_size_gb     = var.redis_memory_gb
  redis_version      = "REDIS_7_2"
  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  depends_on         = [google_service_networking_connection.private]
}

# ---------------- Secrets ----------------
# Note: generated values (DB password, signing key) are stored in Terraform state.
# Keep state in a locked-down GCS bucket.

resource "google_secret_manager_secret" "gemini" {
  secret_id = "gemini-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
# The Gemini key version is added by hand (docs/DEPLOY.md) so it never enters Terraform state.

resource "random_password" "trippass" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret" "trippass" {
  secret_id = "trippass-signing-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "trippass" {
  secret      = google_secret_manager_secret.trippass.id
  secret_data = random_password.trippass.result
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${google_sql_user.app.name}:${random_password.db.result}@${google_sql_database_instance.pg.private_ip_address}:5432/${google_sql_database.app.name}"
}

resource "google_secret_manager_secret" "redis_url" {
  secret_id = "redis-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "redis_url" {
  secret      = google_secret_manager_secret.redis_url.id
  secret_data = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}/0"
}

# ---------------- Artifact Registry ----------------

resource "google_artifact_registry_repository" "images" {
  repository_id = local.name
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# ---------------- Cloud Run service ----------------

resource "google_service_account" "api" {
  account_id   = "${local.name}-api"
  display_name = "KogniSync API (Cloud Run)"
}

resource "google_secret_manager_secret_iam_member" "api_access" {
  for_each = {
    gemini   = google_secret_manager_secret.gemini.id
    trippass = google_secret_manager_secret.trippass.id
    database = google_secret_manager_secret.database_url.id
    redis    = google_secret_manager_secret.redis_url.id
  }
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "${local.name}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.run.id
      }
      egress = "PRIVATE_RANGES_ONLY" # Gemini and other public APIs still go out directly
    }

    containers {
      image = var.api_image

      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GEMINI_OMNI_MODEL"
        value = var.gemini_omni_model
      }
      env {
        name  = "ENABLE_SIMULATION"
        value = tostring(var.enable_simulation)
      }

      dynamic "env" {
        for_each = {
          GEMINI_API_KEY       = google_secret_manager_secret.gemini.secret_id
          TRIPPASS_SIGNING_KEY = google_secret_manager_secret.trippass.secret_id
          DATABASE_URL         = google_secret_manager_secret.database_url.secret_id
          REDIS_URL            = google_secret_manager_secret.redis_url.secret_id
        }
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/v1/health"
        }
        period_seconds    = 5
        failure_threshold = 6
      }

      liveness_probe {
        http_get {
          path = "/api/v1/health"
        }
        period_seconds = 30
      }
    }
  }

  lifecycle {
    # Cloud Build deploys new images; don't roll them back on the next terraform apply.
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [
    google_secret_manager_secret_iam_member.api_access,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.redis_url,
    google_secret_manager_secret_version.trippass,
  ]
}

# Public API (the web app calls it through Firebase Hosting). Add API Gateway / Cloud Armor
# in front before real traffic.
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

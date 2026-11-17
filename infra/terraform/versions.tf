terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # Use a GCS bucket for shared state (create it once, by hand):
  # backend "gcs" {
  #   bucket = "YOUR_PROJECT-tfstate"
  #   prefix = "kognisync"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

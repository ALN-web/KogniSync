variable "project_id" {
  description = "Google Cloud project id"
  type        = string
}

variable "region" {
  description = "Primary region (Mumbai)"
  type        = string
  default     = "asia-south1"
}

variable "api_image" {
  description = "Initial API image. Cloud Build updates it on every deploy (Terraform ignores later changes)."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "cors_origins" {
  description = "Comma-separated web origins allowed to call the API directly"
  type        = string
  default     = ""
}

variable "gemini_model" {
  type    = string
  default = "gemini-2.5-flash"
}

variable "gemini_omni_model" {
  type    = string
  default = "gemini-2.5-flash"
}

variable "db_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-custom-1-3840"
}

variable "db_high_availability" {
  description = "REGIONAL (HA, standby in a second zone) instead of ZONAL. Roughly doubles DB cost."
  type        = bool
  default     = false
}

variable "redis_tier" {
  description = "BASIC (single node) or STANDARD_HA (replica + failover)"
  type        = string
  default     = "BASIC"
}

variable "redis_memory_gb" {
  type    = number
  default = 1
}

variable "min_instances" {
  description = "Keep >= 1 for a demo to avoid cold starts"
  type        = number
  default     = 0
}

variable "max_instances" {
  type    = number
  default = 10
}

variable "enable_simulation" {
  description = "Allow the disruption-simulation API (demo only)"
  type        = bool
  default     = false
}

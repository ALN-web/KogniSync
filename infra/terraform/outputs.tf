output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "sql_instance" {
  value = google_sql_database_instance.pg.connection_name
}

output "redis_host" {
  value = google_redis_instance.cache.host
}

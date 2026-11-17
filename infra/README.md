# infra

Google Cloud deployment for KogniSync in `asia-south1` (Mumbai). Prepared but not applied.

- `terraform/`: Cloud Run, Cloud SQL for PostgreSQL (private IP), Memorystore for Redis,
  Secret Manager, Artifact Registry, VPC with private services access, service account.
- `cloudbuild.yaml`: runs both test suites, builds and pushes the API image, deploys to
  Cloud Run.
- Firebase Hosting config lives in `frontend/firebase.json`.

Step-by-step instructions, costs and what is not built yet: [docs/DEPLOY.md](../docs/DEPLOY.md).

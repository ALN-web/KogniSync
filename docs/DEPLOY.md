# Deploying KogniSync to Google Cloud

**Status: prepared, not deployed.** Nothing in this repo has been applied to a Google Cloud
project. The Terraform has not been run through `terraform validate` (Terraform was not
installed on the build machine), and the Docker image has not been built locally (Docker was
not installed). Expect to fix small issues on the first run.

## What gets created

Region `asia-south1` (Mumbai). See [infra/terraform/main.tf](../infra/terraform/main.tf).

| Piece | Service | Notes |
|---|---|---|
| API | Cloud Run `kognisync-api` | FastAPI container, Direct VPC egress, health probes on `/api/v1/health` |
| Database | Cloud SQL for PostgreSQL 16 | Private IP only, backups + PITR, optional HA (`db_high_availability`) |
| Holds, idempotency keys, cache | Memorystore for Redis 7.2 | Private service access; `STANDARD_HA` tier optional |
| Secrets | Secret Manager | `gemini-api-key`, `trippass-signing-key`, `database-url`, `redis-url` |
| Images | Artifact Registry `kognisync` | |
| Web app | Firebase Hosting | Rewrites `/api/**` to Cloud Run, so the app and API share one origin |
| CI/CD | Cloud Build ([infra/cloudbuild.yaml](../infra/cloudbuild.yaml)) | Tests, builds, pushes and deploys |

**Cost warning:** Cloud SQL and Memorystore bill for every hour they exist, even with no
traffic. HA tiers cost roughly double. Check the
[pricing calculator](https://cloud.google.com/products/calculator) and run
`terraform destroy` after the demo (Cloud SQL has `deletion_protection = true`; set it to
false first).

## Not built yet (from the architecture slide)

- GKE Autopilot + Valhalla routing, Pub/Sub + Cloud Scheduler feed polling, BigQuery,
  API Gateway, Cloud Armor, and the `asia-south2` failover region. The app uses mock
  providers, so there are no live feeds to poll yet.
- Gemini is called through the Gemini API with an API key. Switching to Vertex AI
  (service-account auth, no key) is a small change in `app/ai/llm.py`: create the client with
  `genai.Client(vertexai=True, project=..., location=...)`.

## Prerequisites

- `gcloud` CLI, Terraform 1.6+, Node 20+ (for `firebase-tools`)
- A Google Cloud project with billing enabled, and Owner (or equivalent) on it
- A Gemini API key from Google AI Studio

## Steps

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 1. Create the secret containers, then add the Gemini key by hand

The Gemini key is added outside Terraform so it never lands in Terraform state.

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # edit project_id and cors_origins
terraform init
terraform apply -target=google_secret_manager_secret.gemini
```

```bash
printf '%s' "YOUR_GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
```

### 2. Create everything else

```bash
terraform apply
```

This takes 10–20 minutes (Cloud SQL and Redis are slow to create). Cloud Run starts with a
placeholder image.

### 3. Let Cloud Build deploy

Grant the Cloud Build service account permission to deploy (once):

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" --role=roles/run.admin
gcloud iam service-accounts add-iam-policy-binding kognisync-api@YOUR_PROJECT_ID.iam.gserviceaccount.com --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" --role=roles/iam.serviceAccountUser
```

From the repo root:

```bash
gcloud builds submit --config infra/cloudbuild.yaml .
```

Check it:

```bash
curl "$(terraform -chdir=infra/terraform output -raw api_url)/api/v1/health/ready"
```

All of `postgres`, `redis` and `gemini` should report `ok`.

### 4. Deploy the web app

```bash
cd frontend
cp .firebaserc.example .firebaserc   # set your project id
npm ci && npm run build
npx firebase-tools login
npx firebase-tools deploy --only hosting
```

The site is at `https://YOUR_PROJECT_ID.web.app`. `/api/**` is forwarded to Cloud Run.

## Configuration reference

| Variable | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Secret Manager | Enables the Gemini copilot, voice and photo input |
| `GEMINI_MODEL`, `GEMINI_OMNI_MODEL` | Terraform vars | Model ids; update as new Gemini models ship |
| `TRIPPASS_SIGNING_KEY` | Secret Manager (generated) | Signs TripPass QR tokens; required when `APP_ENV=production` |
| `DATABASE_URL` | Secret Manager (generated) | TripPass storage in Cloud SQL |
| `REDIS_URL` | Secret Manager (generated) | Holds, inventory, idempotency keys, journey cache |
| `ENABLE_SIMULATION` | Terraform var | Allows `POST /api/v1/disruptions` for demos; keep `false` in production |

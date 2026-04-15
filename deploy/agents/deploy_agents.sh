#!/bin/bash
# deploy_agents.sh — Build & deploy all 4 Raito agents as Cloud Run Jobs
# Run from the project root: bash deploy/agents/deploy_agents.sh

set -euo pipefail

PROJECT="raito-house-of-brands"
REGION="me-west1"
REPO="raito-repo"
IMAGE="me-west1-docker.pkg.dev/${PROJECT}/${REPO}/raito-agents:latest"
SA="raito-agent-runner@${PROJECT}.iam.gserviceaccount.com"

# ── 0. Ensure service account exists ────────────────────────────────────────
echo "Checking service account …"
# Use create with 2>&1 and ignore "already exists" errors — safer than describe+create
gcloud iam service-accounts create "raito-agent-runner" \
  --project="${PROJECT}" \
  --display-name="Raito Agent Runner" 2>&1 \
  | grep -v "already exists" || true
echo "✅ Service account ready (${SA})"

# Grant required roles
for ROLE in \
  "roles/run.invoker" \
  "roles/cloudsql.client" \
  "roles/logging.viewer" \
  "roles/secretmanager.secretAccessor" \
  "roles/cloudscheduler.jobRunner" \
  "roles/storage.objectViewer"; do
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${SA}" \
    --role="${ROLE}" \
    --quiet 2>/dev/null || true
done
echo "✅ Service account ready"

# ── 1. Build & Push ─────────────────────────────────────────────────────────
echo ""
echo "Building agent image …"
docker build --platform linux/amd64 \
  -f deploy/agents/Dockerfile.agents \
  -t "${IMAGE}" .
docker push "${IMAGE}"
echo "Image pushed → ${IMAGE}"

# ── 2. Ensure secrets exist (create with placeholder if missing) ─────────────
ensure_secret() {
  local SECRET_NAME="$1"
  if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT}" &>/dev/null; then
    echo "Creating secret ${SECRET_NAME} (set the real value in Secret Manager) …"
    echo "PLACEHOLDER" | gcloud secrets create "${SECRET_NAME}" \
      --project="${PROJECT}" \
      --data-file=- \
      --replication-policy="automatic"
  fi
}
ensure_secret "raito-db-url"
ensure_secret "raito-slack-webhook"

# ── 3. Create/update Cloud Run Jobs ─────────────────────────────────────────
create_or_update_job() {
  local JOB_NAME="$1"
  local AGENT_NAME="$2"
  local SCHEDULE="$3"
  local DESCRIPTION="$4"

  echo ""
  echo "Deploying job: ${JOB_NAME} (${AGENT_NAME}) …"

  # Check if job already exists
  if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT}" &>/dev/null; then
    echo "  → Updating existing job …"
    gcloud run jobs update "${JOB_NAME}" \
      --image="${IMAGE}" \
      --region="${REGION}" \
      --project="${PROJECT}" \
      --service-account="${SA}" \
      --set-env-vars="AGENT_NAME=${AGENT_NAME},GCP_PROJECT=${PROJECT},GCP_REGION=${REGION}" \
      --set-secrets="DATABASE_URL=raito-db-url:latest,RAITO_SLACK_WEBHOOK=raito-slack-webhook:latest" \
      --set-cloudsql-instances="${PROJECT}:${REGION}:raito-db" \
      --memory="512Mi" \
      --cpu="1" \
      --task-timeout="600s" \
      --max-retries=2
  else
    echo "  → Creating new job …"
    gcloud run jobs create "${JOB_NAME}" \
      --image="${IMAGE}" \
      --region="${REGION}" \
      --project="${PROJECT}" \
      --service-account="${SA}" \
      --set-env-vars="AGENT_NAME=${AGENT_NAME},GCP_PROJECT=${PROJECT},GCP_REGION=${REGION}" \
      --set-secrets="DATABASE_URL=raito-db-url:latest,RAITO_SLACK_WEBHOOK=raito-slack-webhook:latest" \
      --set-cloudsql-instances="${PROJECT}:${REGION}:raito-db" \
      --memory="512Mi" \
      --cpu="1" \
      --task-timeout="600s" \
      --max-retries=2
  fi

  # Cloud Scheduler: create or update
  local TRIGGER_NAME="trigger-${JOB_NAME}"
  local JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB_NAME}:run"

  if gcloud scheduler jobs describe "${TRIGGER_NAME}" --location="${REGION}" --project="${PROJECT}" &>/dev/null; then
    echo "  → Updating scheduler trigger …"
    gcloud scheduler jobs update http "${TRIGGER_NAME}" \
      --location="${REGION}" \
      --project="${PROJECT}" \
      --schedule="${SCHEDULE}" \
      --time-zone="Asia/Jerusalem" \
      --uri="${JOB_URI}"
  else
    echo "  → Creating scheduler trigger …"
    gcloud scheduler jobs create http "${TRIGGER_NAME}" \
      --location="${REGION}" \
      --project="${PROJECT}" \
      --schedule="${SCHEDULE}" \
      --time-zone="Asia/Jerusalem" \
      --uri="${JOB_URI}" \
      --http-method=POST \
      --oauth-service-account-email="${SA}" \
      --description="${DESCRIPTION}"
  fi

  echo "✅ ${JOB_NAME} deployed + scheduled (${SCHEDULE})"
}

# ── 4. Deploy each agent ─────────────────────────────────────────────────────

create_or_update_job \
  "raito-data-steward" \
  "data_steward" \
  "*/30 * * * *" \
  "Raito Data Steward — ingests new distributor files every 30 min"

create_or_update_job \
  "raito-insight-analyst" \
  "insight_analyst" \
  "0 6 * * 0" \
  "Raito Insight Analyst — weekly intelligence report every Sunday 06:00"

create_or_update_job \
  "raito-devops-watchdog" \
  "devops_watchdog" \
  "*/10 * * * *" \
  "Raito DevOps Watchdog — monitors Cloud Run + DB health every 10 min"

create_or_update_job \
  "raito-ux-architect" \
  "ux_architect" \
  "0 7 * * 1" \
  "Raito UX Architect — weekly frontend proposals every Monday 07:00"

create_or_update_job \
  "raito-qa-agent" \
  "qa_agent" \
  "0 8 * * *" \
  "Raito QA Agent — daily dashboard validation at 08:00 IL time"

echo ""
echo "════════════════════════════════════════════════"
echo "All 5 agents deployed!"
echo ""
echo "⚠  Set real secret values in GCP Secret Manager:"
echo "   gcloud secrets versions add raito-db-url --data-file=- <<< 'postgresql://user:pass@/db?host=/cloudsql/...'"
echo "   gcloud secrets versions add raito-slack-webhook --data-file=- <<< 'https://hooks.slack.com/...'"
echo ""
echo "Run any agent manually:"
echo "  gcloud run jobs execute raito-data-steward --region=${REGION} --project=${PROJECT}"
echo "  gcloud run jobs execute raito-insight-analyst --region=${REGION} --project=${PROJECT}"
echo "  gcloud run jobs execute raito-devops-watchdog --region=${REGION} --project=${PROJECT}"
echo "  gcloud run jobs execute raito-ux-architect --region=${REGION} --project=${PROJECT}"
echo "  gcloud run jobs execute raito-qa-agent --region=${REGION} --project=${PROJECT}"
echo "════════════════════════════════════════════════"

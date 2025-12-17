#!/bin/bash
# =============================================================================
# Deploy New Users Report to Cloud Run
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load configuration
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PROJECT_ID="${GCP_PROJECT_ID:-stagelync-daily-user-reports}"
REGION="${GCP_REGION:-asia-northeast1}"

# Service
SERVICE_NAME="new-users-report"
SCHEDULER_NAME="new-users-report-daily"
SCHEDULE="${SCHEDULE_NEW_USERS:-0 8 * * *}"
TIMEZONE="${TIMEZONE:-Asia/Tokyo}"

# VPN (from bartoss-project-vpn)
VPN_PROJECT="${VPN_PROJECT_ID:-bartoss-project-vpn}"
VPC_CONNECTOR_NAME="${VPC_CONNECTOR_NAME:-bartoss-connector}"
VPC_CONNECTOR="projects/$VPN_PROJECT/locations/$REGION/connectors/$VPC_CONNECTOR_NAME"

# App settings
EMAIL_TO="${EMAIL_TO:-laci@stagelync.com}"
SPREADSHEET_NAME="${SHEET_NEW_USERS:-StageLync - New Users Report}"

# -----------------------------------------------------------------------------
# Script
# -----------------------------------------------------------------------------

echo "============================================================"
echo "Deploying: $SERVICE_NAME"
echo "============================================================"
echo "Project:    $PROJECT_ID"
echo "Region:     $REGION"
echo "Schedule:   $SCHEDULE ($TIMEZONE)"
echo "VPN:        $VPN_PROJECT"
echo "============================================================"
echo ""

gcloud config set project $PROJECT_ID

# -----------------------------------------------------------------------------
# Prepare Build Context
# -----------------------------------------------------------------------------
echo "=== Preparing build context ==="

# Create temp build directory
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy files
cp "$SCRIPT_DIR/main.py" "$BUILD_DIR/"
cp "$SCRIPT_DIR/Dockerfile" "$BUILD_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/shared" "$BUILD_DIR/"

echo "Build context ready: $BUILD_DIR"

# -----------------------------------------------------------------------------
# Deploy to Cloud Run
# -----------------------------------------------------------------------------
echo ""
echo "=== Deploying to Cloud Run ==="

cd "$BUILD_DIR"

gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --no-allow-unauthenticated \
    --memory 512Mi \
    --timeout 300 \
    --min-instances 0 \
    --max-instances 1 \
    --vpc-connector $VPC_CONNECTOR \
    --vpc-egress all-traffic \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,EMAIL_TO=$EMAIL_TO,SPREADSHEET_NAME=$SPREADSHEET_NAME,MYSQL_PORT=3306,LOG_LEVEL=INFO"

# Get service URL and SA
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
SA_EMAIL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(spec.template.spec.serviceAccountName)')

if [ -z "$SA_EMAIL" ]; then
    SA_EMAIL="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
fi

echo ""
echo "Service URL: $SERVICE_URL"
echo "Service Account: $SA_EMAIL"

# -----------------------------------------------------------------------------
# Grant Permissions
# -----------------------------------------------------------------------------
echo ""
echo "=== Granting permissions ==="

# Secret Manager access
for secret in mysql-host mysql-user mysql-password mysql-database smtp-user smtp-password; do
    if gcloud secrets describe $secret &>/dev/null; then
        gcloud secrets add-iam-policy-binding $secret \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
        echo "  ✓ $secret"
    fi
done

# -----------------------------------------------------------------------------
# Cloud Scheduler
# -----------------------------------------------------------------------------
echo ""
echo "=== Setting up Cloud Scheduler ==="

# Delete existing scheduler if exists
gcloud scheduler jobs delete $SCHEDULER_NAME --location $REGION --quiet 2>/dev/null || true

# Create scheduler job
gcloud scheduler jobs create http $SCHEDULER_NAME \
    --location $REGION \
    --schedule "$SCHEDULE" \
    --time-zone "$TIMEZONE" \
    --uri "$SERVICE_URL" \
    --http-method POST \
    --oidc-service-account-email "$SA_EMAIL" \
    --oidc-token-audience "$SERVICE_URL" \
    --attempt-deadline 300s

echo "  ✓ Scheduler created: $SCHEDULER_NAME"

# -----------------------------------------------------------------------------
# Monitoring Alert
# -----------------------------------------------------------------------------
echo ""
echo "=== Setting up Monitoring ==="

# Create alert policy for failures
cat > /tmp/alert-policy.json << EOF
{
  "displayName": "$SERVICE_NAME - Execution Failures",
  "conditions": [
    {
      "displayName": "Error Rate > 0",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "0s",
        "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_COUNT"}]
      }
    }
  ],
  "combiner": "OR",
  "enabled": true
}
EOF

gcloud alpha monitoring policies create --policy-from-file=/tmp/alert-policy.json 2>/dev/null || \
    echo "  Alert policy may already exist"

# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "                 DEPLOYMENT COMPLETE"
echo "============================================================"
echo ""
echo "Service URL:  $SERVICE_URL"
echo "Schedule:     $SCHEDULE ($TIMEZONE)"
echo ""
echo "============================================================"
echo "                    ENDPOINTS"
echo "============================================================"
echo ""
echo "Scheduled trigger (by Cloud Scheduler):"
echo "  POST $SERVICE_URL/"
echo ""
echo "Manual trigger:"
echo "  curl -X POST -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" $SERVICE_URL/run"
echo ""
echo "Health check:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "Status:"
echo "  curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" $SERVICE_URL/status"
echo ""
echo "============================================================"
echo "                    QUICK COMMANDS"
echo "============================================================"
echo ""
echo "Test now:"
echo "  gcloud scheduler jobs run $SCHEDULER_NAME --location $REGION"
echo ""
echo "View logs:"
echo "  gcloud logging read 'resource.labels.service_name=$SERVICE_NAME' --limit 20"
echo ""
echo "============================================================"

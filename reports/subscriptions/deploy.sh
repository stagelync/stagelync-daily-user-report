#!/bin/bash
# =============================================================================
# Deploy Subscriptions Report to Cloud Run
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
SERVICE_NAME="subscriptions-report"
SCHEDULER_NAME="subscriptions-report-daily"
SCHEDULE="${SCHEDULE_SUBSCRIPTIONS:-0 8 * * *}"
TIMEZONE="${TIMEZONE:-Asia/Tokyo}"

# VPN
VPN_PROJECT="${VPN_PROJECT_ID:-bartoss-project-vpn}"
VPC_CONNECTOR="projects/$VPN_PROJECT/locations/$REGION/connectors/${VPC_CONNECTOR_NAME:-bartoss-connector}"

# App settings
EMAIL_TO="${EMAIL_TO:-laci@stagelync.com}"
SPREADSHEET_NAME="${SHEET_SUBSCRIPTIONS:-StageLync - Subscriptions Report}"

# -----------------------------------------------------------------------------
# Script (same as new-users deploy.sh)
# -----------------------------------------------------------------------------

echo "============================================================"
echo "Deploying: $SERVICE_NAME"
echo "============================================================"

gcloud config set project $PROJECT_ID

# Prepare build context
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

cp "$SCRIPT_DIR/main.py" "$BUILD_DIR/"
cp "$SCRIPT_DIR/Dockerfile" "$BUILD_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/shared" "$BUILD_DIR/"

cd "$BUILD_DIR"

# Deploy
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --no-allow-unauthenticated \
    --memory 512Mi \
    --timeout 300 \
    --vpc-connector $VPC_CONNECTOR \
    --vpc-egress all-traffic \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,EMAIL_TO=$EMAIL_TO,SPREADSHEET_NAME=$SPREADSHEET_NAME,MYSQL_PORT=3306,LOG_LEVEL=INFO"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
SA_EMAIL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(spec.template.spec.serviceAccountName)')
[ -z "$SA_EMAIL" ] && SA_EMAIL="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

# Grant secret access
for secret in mysql-host mysql-user mysql-password mysql-database smtp-user smtp-password; do
    gcloud secrets add-iam-policy-binding $secret --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
done

# Create scheduler
gcloud scheduler jobs delete $SCHEDULER_NAME --location $REGION --quiet 2>/dev/null || true
gcloud scheduler jobs create http $SCHEDULER_NAME \
    --location $REGION \
    --schedule "$SCHEDULE" \
    --time-zone "$TIMEZONE" \
    --uri "$SERVICE_URL" \
    --http-method POST \
    --oidc-service-account-email "$SA_EMAIL" \
    --oidc-token-audience "$SERVICE_URL"

echo ""
echo "============================================================"
echo "Deployed: $SERVICE_URL"
echo "Schedule: $SCHEDULE ($TIMEZONE)"
echo "Test: gcloud scheduler jobs run $SCHEDULER_NAME --location $REGION"
echo "============================================================"

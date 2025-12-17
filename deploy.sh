#!/bin/bash
# =============================================================================
# Deploy Daily New Users Report to Google Cloud
# Cloud Run + Cloud Scheduler + Cloud Monitoring
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# CONFIGURATION - Edit these values
# -----------------------------------------------------------------------------
PROJECT_ID="stagelync-dev-opensearch"
REGION="asia-northeast1"  # Tokyo
SERVICE_NAME="daily-users-report"
SCHEDULER_NAME="daily-users-report-trigger"

# MySQL Configuration (will be stored in Secret Manager)
MYSQL_HOST="circustalk-do-user-3484213-0.b.db.ondigitalocean.com"
MYSQL_USER="laci"

MYSQL_DATABASE="defaultdb"

# SMTP Configuration (will be stored in Secret Manager)
SMTP_USER="laci@stagelync.com"


# Email recipient
EMAIL_TO="laci@stagelync.com"
SPREADSHEET_NAME="Daily New Users Report"

# Schedule (8 AM Tokyo time)
SCHEDULE="0 8 * * *"
TIMEZONE="Asia/Tokyo"

# -----------------------------------------------------------------------------
# Script starts here
# -----------------------------------------------------------------------------

echo "=== Setting up GCP project ==="
gcloud config set project $PROJECT_ID

echo "=== Enabling required APIs ==="
gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    cloudbuild.googleapis.com \
    sheets.googleapis.com \
    drive.googleapis.com

echo "=== Creating secrets in Secret Manager ==="
# Function to create or update secret
create_secret() {
    local name=$1
    local value=$2
    
    if gcloud secrets describe $name --project=$PROJECT_ID &>/dev/null; then
        echo "$value" | gcloud secrets versions add $name --data-file=-
        echo "Updated secret: $name"
    else
        echo "$value" | gcloud secrets create $name --data-file=- --replication-policy="automatic"
        echo "Created secret: $name"
    fi
}

create_secret "mysql-host" "$MYSQL_HOST"
create_secret "mysql-user" "$MYSQL_USER"
create_secret "mysql-password" "$MYSQL_PASSWORD"
create_secret "mysql-database" "$MYSQL_DATABASE"
create_secret "smtp-user" "$SMTP_USER"
create_secret "smtp-password" "$SMTP_PASSWORD"

echo "=== Building and deploying to Cloud Run ==="
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --no-allow-unauthenticated \
    --memory 512Mi \
    --timeout 300 \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,EMAIL_TO=$EMAIL_TO,SPREADSHEET_NAME=$SPREADSHEET_NAME,MYSQL_PORT=3306" \
    --service-account "$SERVICE_NAME-sa@$PROJECT_ID.iam.gserviceaccount.com" 2>/dev/null || \
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --no-allow-unauthenticated \
    --memory 512Mi \
    --timeout 300 \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,EMAIL_TO=$EMAIL_TO,SPREADSHEET_NAME=$SPREADSHEET_NAME,MYSQL_PORT=3306"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "Service deployed at: $SERVICE_URL"

echo "=== Setting up Service Account permissions ==="
# Get the default compute service account
SA_EMAIL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(spec.template.spec.serviceAccountName)')

if [ -z "$SA_EMAIL" ]; then
    SA_EMAIL="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
fi

echo "Service Account: $SA_EMAIL"

# Grant Secret Manager access
gcloud secrets add-iam-policy-binding mysql-host --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding mysql-user --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding mysql-password --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding mysql-database --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding smtp-user --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding smtp-password --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor" --quiet

echo "=== Creating Cloud Scheduler job ==="
# Delete existing scheduler if it exists
gcloud scheduler jobs delete $SCHEDULER_NAME --location $REGION --quiet 2>/dev/null || true

# Create scheduler job
gcloud scheduler jobs create http $SCHEDULER_NAME \
    --location $REGION \
    --schedule "$SCHEDULE" \
    --time-zone "$TIMEZONE" \
    --uri "$SERVICE_URL" \
    --http-method POST \
    --oidc-service-account-email "$SA_EMAIL" \
    --oidc-token-audience "$SERVICE_URL"

echo "=== Creating Alert Policy for failures ==="
cat > /tmp/alert-policy.json << EOF
{
  "displayName": "Daily Users Report - Execution Failures",
  "conditions": [
    {
      "displayName": "Cloud Run Error Rate",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "0s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_COUNT"
          }
        ]
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "604800s"
  },
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": []
}
EOF

# Create the alert policy
gcloud alpha monitoring policies create --policy-from-file=/tmp/alert-policy.json 2>/dev/null || \
    echo "Note: Alert policy creation requires additional setup. See documentation."

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Cloud Run Service: $SERVICE_URL"
echo "Scheduler Job: $SCHEDULER_NAME (runs at $SCHEDULE $TIMEZONE)"
echo ""
echo "Next steps:"
echo "1. Set up notification channels in Cloud Monitoring for alerts"
echo "2. Test manually: gcloud scheduler jobs run $SCHEDULER_NAME --location $REGION"
echo "3. View logs: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --limit 50"
echo ""
echo "Important: Make sure your MySQL server allows connections from Cloud Run's IP ranges"
echo "or use Cloud SQL with VPC connector for private connectivity."

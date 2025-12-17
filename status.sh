#!/bin/bash
# =============================================================================
# StageLync Reports - Status Check
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"

PROJECT_ID="${GCP_PROJECT_ID:-stagelync-daily-user-reports}"
REGION="${GCP_REGION:-asia-northeast1}"

echo "============================================================"
echo "StageLync Reports - Status"
echo "============================================================"
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo "============================================================"

gcloud config set project $PROJECT_ID --quiet

# -----------------------------------------------------------------------------
# Cloud Run Services
# -----------------------------------------------------------------------------
echo ""
echo "=== Cloud Run Services ==="
SERVICES=$(gcloud run services list --region=$REGION --format='value(metadata.name)' 2>/dev/null)

if [ -n "$SERVICES" ]; then
    for svc in $SERVICES; do
        URL=$(gcloud run services describe $svc --region=$REGION --format='value(status.url)')
        echo "  ✓ $svc"
        echo "    $URL"
    done
else
    echo "  No services deployed"
fi

# -----------------------------------------------------------------------------
# Cloud Scheduler Jobs
# -----------------------------------------------------------------------------
echo ""
echo "=== Scheduled Jobs ==="
gcloud scheduler jobs list --location=$REGION --format="table(
    name.basename(),
    schedule,
    state,
    lastAttemptTime.date('%Y-%m-%d %H:%M')
)" 2>/dev/null || echo "  No scheduler jobs"

# -----------------------------------------------------------------------------
# Secrets
# -----------------------------------------------------------------------------
echo ""
echo "=== Secrets ==="
for secret in mysql-host mysql-user mysql-password mysql-database smtp-user smtp-password; do
    if gcloud secrets describe $secret &>/dev/null 2>&1; then
        echo "  ✓ $secret"
    else
        echo "  ✗ $secret (not found)"
    fi
done

# -----------------------------------------------------------------------------
# Recent Logs
# -----------------------------------------------------------------------------
echo ""
echo "=== Recent Activity (last 5 executions) ==="
gcloud logging read "
    resource.type=\"cloud_run_revision\"
    textPayload:\"Report\"
" --limit=5 --format="table(
    timestamp.date('%Y-%m-%d %H:%M'),
    resource.labels.service_name,
    textPayload
)" 2>/dev/null || echo "  No recent logs"

# -----------------------------------------------------------------------------
# Quick Links
# -----------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "                    Quick Links"
echo "============================================================"
echo ""
echo "Cloud Run:   https://console.cloud.google.com/run?project=$PROJECT_ID"
echo "Scheduler:   https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID"
echo "Logs:        https://console.cloud.google.com/logs?project=$PROJECT_ID"
echo "Monitoring:  https://console.cloud.google.com/monitoring?project=$PROJECT_ID"
echo ""

#!/bin/bash
# =============================================================================
# StageLync Reports - Manual Trigger
# 
# Usage:
#   ./trigger.sh new-users       # Trigger new users report
#   ./trigger.sh subscriptions   # Trigger subscriptions report
#   ./trigger.sh all             # Trigger all reports
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"

PROJECT_ID="${GCP_PROJECT_ID:-stagelync-daily-user-reports}"
REGION="${GCP_REGION:-asia-northeast1}"

if [ -z "$1" ]; then
    echo "Usage: ./trigger.sh <report-name>"
    echo ""
    echo "Available reports:"
    echo "  new-users       - New users daily report"
    echo "  subscriptions   - Subscriptions daily report"
    echo "  all             - All reports"
    echo ""
    echo "Options:"
    echo "  --scheduler     - Use Cloud Scheduler (default: direct HTTP call)"
    exit 1
fi

REPORT="$1"
USE_SCHEDULER=false

if [[ "$*" == *"--scheduler"* ]]; then
    USE_SCHEDULER=true
fi

gcloud config set project $PROJECT_ID --quiet

trigger_report() {
    local service_name=$1
    local scheduler_name=$2
    
    echo "Triggering: $service_name"
    
    if [ "$USE_SCHEDULER" = true ]; then
        # Use Cloud Scheduler
        echo "  Method: Cloud Scheduler"
        gcloud scheduler jobs run $scheduler_name --location $REGION
    else
        # Direct HTTP call
        SERVICE_URL=$(gcloud run services describe $service_name --region $REGION --format='value(status.url)' 2>/dev/null)
        
        if [ -z "$SERVICE_URL" ]; then
            echo "  ✗ Service not found"
            return 1
        fi
        
        echo "  Method: Direct HTTP"
        echo "  URL: $SERVICE_URL/run"
        
        # Get identity token
        TOKEN=$(gcloud auth print-identity-token)
        
        # Call the /run endpoint
        RESPONSE=$(curl -s -X POST \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            "$SERVICE_URL/run")
        
        echo "  Response: $RESPONSE"
    fi
    
    echo ""
}

case "$REPORT" in
    new-users)
        trigger_report "new-users-report" "new-users-report-daily"
        ;;
    subscriptions)
        trigger_report "subscriptions-report" "subscriptions-report-daily"
        ;;
    all)
        trigger_report "new-users-report" "new-users-report-daily"
        trigger_report "subscriptions-report" "subscriptions-report-daily"
        ;;
    *)
        echo "Unknown report: $REPORT"
        exit 1
        ;;
esac

echo "Done. Check logs:"
echo "  gcloud logging read 'resource.type=cloud_run_revision' --limit 10"

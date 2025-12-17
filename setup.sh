#!/bin/bash
# =============================================================================
# StageLync Daily Reports - Project Setup
# Run this ONCE to set up the project and secrets
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load configuration if exists
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"

PROJECT_ID="${GCP_PROJECT_ID:-stagelync-daily-user-reports}"
REGION="${GCP_REGION:-asia-northeast1}"

echo "============================================================"
echo "StageLync Reports - Project Setup"
echo "============================================================"
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo "============================================================"
echo ""

# Check for .env file
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "No .env file found."
    echo ""
    read -p "Create .env from template? (y/n): " CREATE_ENV
    if [ "$CREATE_ENV" = "y" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo "Created .env file. Please edit it with your values."
        echo ""
        echo "  nano $SCRIPT_DIR/.env"
        echo ""
        exit 0
    fi
fi

gcloud config set project $PROJECT_ID

# -----------------------------------------------------------------------------
# Enable APIs
# -----------------------------------------------------------------------------
echo "=== Enabling APIs ==="
gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    cloudbuild.googleapis.com \
    sheets.googleapis.com \
    drive.googleapis.com

echo "✓ APIs enabled"

# -----------------------------------------------------------------------------
# Create Secrets
# -----------------------------------------------------------------------------
echo ""
echo "=== Setting Up Secrets ==="
echo "Enter credentials (press Enter to skip if already set)"
echo ""

create_secret() {
    local name=$1
    local prompt=$2
    local env_var=$3
    
    # Check if we have value from .env
    local env_value="${!env_var}"
    
    if gcloud secrets describe $name &>/dev/null 2>&1; then
        if [ -n "$env_value" ]; then
            read -p "$prompt (exists, press Enter to keep or type 'update'): " action
            if [ "$action" = "update" ]; then
                echo "$env_value" | gcloud secrets versions add $name --data-file=-
                echo "  ✓ Updated: $name"
            else
                echo "  ✓ Kept existing: $name"
            fi
        else
            echo "  ✓ Exists: $name"
        fi
    else
        if [ -n "$env_value" ]; then
            echo "$env_value" | gcloud secrets create $name --data-file=- --replication-policy="automatic"
            echo "  ✓ Created: $name"
        else
            read -sp "$prompt: " value
            echo ""
            if [ -n "$value" ]; then
                echo "$value" | gcloud secrets create $name --data-file=- --replication-policy="automatic"
                echo "  ✓ Created: $name"
            else
                echo "  ⚠ Skipped: $name"
            fi
        fi
    fi
}

echo "MySQL Credentials:"
create_secret "mysql-host" "  MySQL Host" "MYSQL_HOST"
create_secret "mysql-user" "  MySQL Username" "MYSQL_USER"
create_secret "mysql-password" "  MySQL Password" "MYSQL_PASSWORD"
create_secret "mysql-database" "  MySQL Database" "MYSQL_DATABASE"

echo ""
echo "SMTP Credentials:"
create_secret "smtp-user" "  SMTP Email" "SMTP_USER"
create_secret "smtp-password" "  SMTP App Password" "SMTP_PASSWORD"

# -----------------------------------------------------------------------------
# Verify VPN Access
# -----------------------------------------------------------------------------
echo ""
echo "=== Verifying VPN Access ==="

VPN_PROJECT="${VPN_PROJECT_ID:-bartoss-project-vpn}"
VPC_CONNECTOR="${VPC_CONNECTOR_NAME:-bartoss-connector}"

if gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR \
    --project=$VPN_PROJECT --region=$REGION &>/dev/null 2>&1; then
    echo "✓ VPN connector accessible: $VPC_CONNECTOR"
else
    echo "⚠ Cannot access VPN connector in $VPN_PROJECT"
    echo "  Make sure bartoss-project-vpn has granted access to this project"
    echo "  Run: ./add-project.sh $PROJECT_ID (in bartoss-project-vpn)"
fi

# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "           PROJECT SETUP COMPLETE"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Test locally:"
echo "     python -m tests.test_local"
echo ""
echo "  2. Deploy reports:"
echo "     cd reports/new-users && ./deploy.sh"
echo ""
echo "  3. Check status:"
echo "     ./status.sh"
echo ""
echo "============================================================"

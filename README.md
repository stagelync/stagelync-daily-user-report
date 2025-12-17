# StageLync Daily Reports

Automated reports running on Google Cloud Run with scheduling, monitoring, and manual triggers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│               stagelync-daily-user-reports                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Cloud Scheduler                       │   │
│  │            (8 AM Tokyo, configurable)                   │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│       ┌────────────────────┼────────────────────┐              │
│       ▼                    ▼                    ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │ New Users   │    │Subscriptions│    │  (Future)   │        │
│  │   Report    │    │   Report    │    │   Reports   │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                  │                  │                │
│         └──────────────────┴──────────────────┘                │
│                            │                                    │
│                    shared/ utilities                           │
│                   (db, email, sheets)                          │
└────────────────────────────┼────────────────────────────────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
         bartoss-project-vpn      Cloud Logging
            (Static IP)           & Monitoring
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌───────┐   ┌─────────┐   ┌─────────┐
│ MySQL │   │  SMTP   │   │ Google  │
│       │   │ (Gmail) │   │ Sheets  │
└───────┘   └─────────┘   └─────────┘
```

## Repository Structure

```
stagelync-daily-user-reports/
├── .env.example          # Configuration template
├── .gitignore            # Git ignore rules
├── requirements.txt      # Local dev dependencies
├── setup.sh              # Project setup script
├── status.sh             # Check deployment status
├── trigger.sh            # Manual trigger script
├── README.md
│
├── shared/               # Reusable utilities
│   ├── __init__.py
│   ├── config.py         # Configuration loading
│   ├── db.py             # Database utilities
│   ├── email_utils.py    # Email utilities
│   ├── sheets.py         # Google Sheets utilities
│   └── logging_config.py # Cloud Logging setup
│
├── tests/
│   └── test_local.py     # Local testing suite
│
└── reports/
    ├── new-users/        # New users report
    │   ├── main.py
    │   ├── deploy.sh
    │   ├── Dockerfile
    │   └── requirements.txt
    │
    └── subscriptions/    # Subscriptions report (template)
        ├── main.py
        ├── deploy.sh
        ├── Dockerfile
        └── requirements.txt
```

## Quick Start

### Prerequisites

1. **VPN must be set up** in `bartoss-project-vpn`
2. **gcloud CLI** installed and authenticated
3. **Python 3.11+** for local testing

### 1. Clone and Configure

```bash
git clone git@github.com:YOUR-USERNAME/stagelync-daily-user-reports.git
cd stagelync-daily-user-reports

# Create configuration
cp .env.example .env
nano .env  # Fill in your values
```

### 2. Local Testing

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run all tests
python -m tests.test_local

# Or test individually
python -m tests.test_local db          # Database only
python -m tests.test_local email       # Email only
python -m tests.test_local sheets      # Google Sheets only
python -m tests.test_local email --send    # Actually send test email
python -m tests.test_local sheets --create # Create test spreadsheet
```

### 3. Deploy

```bash
# Set up project (creates secrets)
./setup.sh

# Deploy new users report
cd reports/new-users
./deploy.sh
```

### 4. Test Deployment

```bash
# Via Cloud Scheduler
gcloud scheduler jobs run new-users-report-daily --location asia-northeast1

# Or direct trigger
./trigger.sh new-users
```

## Configuration

### .env File

```bash
# GCP
GCP_PROJECT_ID="stagelync-daily-user-reports"
GCP_REGION="asia-northeast1"

# VPN
VPN_PROJECT_ID="bartoss-project-vpn"
VPC_CONNECTOR_NAME="bartoss-connector"

# MySQL
MYSQL_HOST="your-mysql-host"
MYSQL_PORT="3306"
MYSQL_USER="your-user"
MYSQL_PASSWORD="your-password"
MYSQL_DATABASE="your-database"

# SMTP
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
EMAIL_TO="laci@stagelync.com"

# Google Sheets
GOOGLE_APPLICATION_CREDENTIALS="./service-account.json"
SHEET_NEW_USERS="StageLync - New Users Report"

# Schedule
SCHEDULE_NEW_USERS="0 8 * * *"
TIMEZONE="Asia/Tokyo"
```

### Google Sheets Setup (Local Testing)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a Service Account
3. Download JSON key as `service-account.json`
4. Set `GOOGLE_APPLICATION_CREDENTIALS=./service-account.json`

## Shared Utilities

### Database (`shared/db`)

```python
from shared import db

# Execute query
users = db.execute_query("SELECT * FROM users WHERE active = 1")

# Get single value
count = db.execute_scalar("SELECT COUNT(*) FROM users")

# With dictionary results
users = db.execute_query("SELECT * FROM users", dictionary=True)
# Returns: [{'id': 1, 'name': 'John'}, ...]

# Test connection
if db.test_connection():
    print("Connected!")
```

### Email (`shared/email_utils`)

```python
from shared import email_utils

# Send simple email
email_utils.send_email(
    to="recipient@example.com",
    subject="Hello",
    body="Email body"
)

# Send report email
email_utils.send_report_email(
    report_name="New Users",
    date="2024-01-15",
    items=["user1", "user2", "user3"]
)

# Test email configuration
email_utils.test_email()
```

### Google Sheets (`shared/sheets`)

```python
from shared import sheets

# Get or create spreadsheet
spreadsheet = sheets.get_or_create_spreadsheet(
    "My Report",
    share_with="laci@stagelync.com"
)

# Add headers
worksheet = spreadsheet.sheet1
sheets.ensure_headers(worksheet, ["Date", "Name", "Value"])

# Append rows
sheets.append_row(worksheet, ["2024-01-15", "Test", 123])
sheets.append_rows(worksheet, [
    ["2024-01-15", "Row 1", 100],
    ["2024-01-15", "Row 2", 200],
])

# Test connection
sheets.test_sheets()
```

## Manual Triggers

### Via Script

```bash
# Trigger specific report
./trigger.sh new-users
./trigger.sh subscriptions

# Trigger all reports
./trigger.sh all

# Use Cloud Scheduler instead of direct HTTP
./trigger.sh new-users --scheduler
```

### Via gcloud

```bash
# Trigger via scheduler
gcloud scheduler jobs run new-users-report-daily --location asia-northeast1

# Direct HTTP call
SERVICE_URL=$(gcloud run services describe new-users-report --region asia-northeast1 --format 'value(status.url)')
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" $SERVICE_URL/run
```

### Endpoints

Each report exposes these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | POST | Scheduled trigger (Cloud Scheduler) |
| `/run` | POST | Manual trigger |
| `/health` | GET | Health check |
| `/status` | GET | Last run info |
| `/test/db` | GET | Test database connection |

## Monitoring

### View Logs

```bash
# All reports
gcloud logging read 'resource.type=cloud_run_revision' --limit 50

# Specific report
gcloud logging read 'resource.labels.service_name=new-users-report' --limit 20

# Errors only
gcloud logging read 'resource.type=cloud_run_revision severity>=ERROR' --limit 10
```

### Cloud Console

- **Logs**: https://console.cloud.google.com/logs?project=stagelync-daily-user-reports
- **Monitoring**: https://console.cloud.google.com/monitoring?project=stagelync-daily-user-reports
- **Cloud Run**: https://console.cloud.google.com/run?project=stagelync-daily-user-reports

### Alerts

Deploy scripts automatically create alert policies for failures. To add notifications:

1. Go to Cloud Monitoring → Alerting
2. Edit the alert policy
3. Add notification channel (email, Slack, etc.)

## Adding New Reports

```bash
# 1. Create report directory
mkdir reports/my-new-report
cd reports/my-new-report

# 2. Copy from template
cp ../new-users/main.py .
cp ../new-users/deploy.sh .
cp ../new-users/Dockerfile .
cp ../new-users/requirements.txt .

# 3. Edit main.py
#    - Change REPORT_NAME
#    - Modify get_data() query
#    - Update email/sheet format

# 4. Edit deploy.sh
#    - Change SERVICE_NAME
#    - Change SCHEDULER_NAME
#    - Update SCHEDULE if needed

# 5. Deploy
./deploy.sh
```

## Cost

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run (per report) | ~$0.00 (free tier) |
| Cloud Scheduler (per job) | $0.10 |
| Secret Manager | ~$0.00 |
| Cloud Logging | ~$0.00 (free tier) |
| **Per Report** | **~$0.10** |

VPN costs (~$1-3/month) are in `bartoss-project-vpn`.

## Troubleshooting

### Local Tests Failing

```bash
# Check configuration
python -m tests.test_local config

# Test components individually
python -m tests.test_local db
python -m tests.test_local email
python -m tests.test_local sheets
```

### Deployment Issues

```bash
# Check VPN access
gcloud compute networks vpc-access connectors describe bartoss-connector \
    --project=bartoss-project-vpn --region=asia-northeast1

# Check secrets exist
gcloud secrets list

# View deployment logs
gcloud logging read 'resource.type=cloud_run_revision severity>=WARNING' --limit 20
```

### Report Not Running

```bash
# Check scheduler status
gcloud scheduler jobs describe new-users-report-daily --location asia-northeast1

# Check last execution
./status.sh

# Manual trigger for debugging
./trigger.sh new-users
```

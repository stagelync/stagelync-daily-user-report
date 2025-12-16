# Daily New Users Report - Google Cloud Deployment

A serverless solution using Cloud Run, Cloud Scheduler, and Cloud Monitoring.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Cloud Scheduler │────▶│   Cloud Run     │────▶│     MySQL       │
│   (8 AM daily)  │     │  (Flask app)    │     │   Database      │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │   Email   │ │  Google   │ │   Cloud   │
            │  (SMTP)   │ │  Sheets   │ │  Logging  │
            └───────────┘ └───────────┘ └───────────┘
                                              │
                                              ▼
                                        ┌───────────┐
                                        │   Cloud   │
                                        │ Monitoring│
                                        │ (Alerts)  │
                                        └───────────┘
```

## Files

| File | Description |
|------|-------------|
| `main.py` | Flask application with Cloud Logging integration |
| `Dockerfile` | Container definition for Cloud Run |
| `requirements.txt` | Python dependencies |
| `deploy.sh` | One-command deployment script |

## Quick Deployment

### 1. Edit Configuration

Open `deploy.sh` and update:

```bash
PROJECT_ID="your-project-id"
REGION="asia-northeast1"  # Tokyo

# MySQL
MYSQL_HOST="your-mysql-host"
MYSQL_USER="your-mysql-user"
MYSQL_PASSWORD="your-mysql-password"
MYSQL_DATABASE="your-database"

# SMTP
SMTP_USER="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
```

### 2. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

This single command:
- Enables all required APIs
- Creates secrets in Secret Manager
- Builds and deploys to Cloud Run
- Sets up Cloud Scheduler for 8 AM Tokyo time
- Creates monitoring alert policy

### 3. Test Manually

```bash
gcloud scheduler jobs run daily-users-report-trigger --location asia-northeast1
```

## Cloud Monitoring Setup

### View Logs

**Cloud Console:**
1. Go to Cloud Run → `daily-users-report` → Logs

**CLI:**
```bash
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=daily-users-report' --limit 50
```

### Custom Log Queries

Find errors:
```
resource.type="cloud_run_revision"
resource.labels.service_name="daily-users-report"
severity>=ERROR
```

Track executions:
```
resource.type="cloud_run_revision"
resource.labels.service_name="daily-users-report"
textPayload:"Report completed successfully"
```

### Set Up Alert Notifications

1. **Go to Cloud Monitoring → Alerting → Notification Channels**

2. **Add Email Channel:**
   - Click "Add New" → Email
   - Enter: `laci@stagelync.com`
   - Verify the email

3. **Update Alert Policy:**
   - Go to Alerting → Policies
   - Find "Daily Users Report - Execution Failures"
   - Edit → Add notification channel

### Create Custom Dashboard

1. Go to Cloud Monitoring → Dashboards → Create Dashboard

2. Add these widgets:

**Execution Count:**
```
resource.type="cloud_run_revision"
metric.type="run.googleapis.com/request_count"
resource.labels.service_name="daily-users-report"
```

**Latency:**
```
resource.type="cloud_run_revision"
metric.type="run.googleapis.com/request_latencies"
resource.labels.service_name="daily-users-report"
```

**Error Rate:**
```
resource.type="cloud_run_revision"
metric.type="run.googleapis.com/request_count"
resource.labels.service_name="daily-users-report"
metric.labels.response_code_class!="2xx"
```

## MySQL Connectivity Options

### Option A: Public MySQL (with SSL)

If your MySQL is publicly accessible, ensure:
1. SSL is enabled
2. Firewall allows Cloud Run IPs (or use 0.0.0.0/0 with strong credentials)

### Option B: Cloud SQL (Recommended)

For Cloud SQL, add VPC connector:

```bash
# Create VPC connector
gcloud compute networks vpc-access connectors create cloudrun-connector \
    --region asia-northeast1 \
    --network default \
    --range 10.8.0.0/28

# Update Cloud Run with connector
gcloud run services update daily-users-report \
    --region asia-northeast1 \
    --vpc-connector cloudrun-connector \
    --set-env-vars "MYSQL_HOST=/cloudsql/PROJECT:REGION:INSTANCE"
```

### Option C: Private MySQL via Cloud VPN

Set up Cloud VPN to your on-premise or other cloud MySQL.

## Cost Estimate

For once-daily execution:

| Service | Monthly Cost |
|---------|-------------|
| Cloud Run | ~$0.00 (free tier covers this) |
| Cloud Scheduler | $0.10 (1 job) |
| Secret Manager | ~$0.00 (6 secrets, minimal access) |
| Cloud Logging | ~$0.00 (minimal logs) |
| **Total** | **~$0.10/month** |

## Troubleshooting

### Check Scheduler Status

```bash
gcloud scheduler jobs describe daily-users-report-trigger --location asia-northeast1
```

### View Recent Executions

```bash
gcloud logging read 'resource.type="cloud_scheduler_job"' --limit 10
```

### Test Cloud Run Directly

```bash
# Get service URL
URL=$(gcloud run services describe daily-users-report --region asia-northeast1 --format 'value(status.url)')

# Get identity token
TOKEN=$(gcloud auth print-identity-token)

# Call the service
curl -X POST -H "Authorization: Bearer $TOKEN" $URL
```

### Common Issues

**"Permission denied" on secrets:**
```bash
# Re-grant permissions
SA_EMAIL="YOUR-PROJECT-NUMBER-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding mysql-password \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
```

**MySQL connection timeout:**
- Check if MySQL allows external connections
- Consider using Cloud SQL with private IP
- Increase Cloud Run timeout if needed

**Google Sheets "not found":**
- The service account needs access to the sheet
- Or let the script create a new one (it will share with laci@stagelync.com)

## Local Development

```bash
# Set environment variables
export GCP_PROJECT_ID="your-project"
export MYSQL_HOST="localhost"
export MYSQL_USER="root"
export MYSQL_PASSWORD="password"
export MYSQL_DATABASE="test"
export SMTP_USER="your@gmail.com"
export SMTP_PASSWORD="app-password"

# Run locally
pip install -r requirements.txt
python main.py

# Test
curl -X POST http://localhost:8080/
```

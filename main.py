#!/usr/bin/env python3
"""
Daily New Users Report - Cloud Run Version
Triggered by Cloud Scheduler, monitored by Cloud Monitoring.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import mysql.connector
import gspread
from google.oauth2 import service_account
from google.cloud import logging as cloud_logging
from google.cloud import secretmanager

# Initialize Flask app
app = Flask(__name__)

# Initialize Cloud Logging
logging_client = cloud_logging.Client()
logging_client.setup_logging()
import logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ID = os.getenv('GCP_PROJECT_ID')
EMAIL_TO = os.getenv('EMAIL_TO', 'laci@stagelync.com')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Daily New Users Report')


def get_secret(secret_id: str) -> str:
    """Retrieve secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def get_mysql_config() -> dict:
    """Get MySQL configuration from environment or Secret Manager."""
    return {
        'host': os.getenv('MYSQL_HOST') or get_secret('mysql-host'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER') or get_secret('mysql-user'),
        'password': os.getenv('MYSQL_PASSWORD') or get_secret('mysql-password'),
        'database': os.getenv('MYSQL_DATABASE') or get_secret('mysql-database'),
    }


def get_smtp_config() -> dict:
    """Get SMTP configuration from environment or Secret Manager."""
    return {
        'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'user': os.getenv('SMTP_USER') or get_secret('smtp-user'),
        'password': os.getenv('SMTP_PASSWORD') or get_secret('smtp-password'),
    }


def get_new_users() -> list[str]:
    """Query MySQL for users created yesterday."""
    query = """
        SELECT username 
        FROM `engine4_users` 
        WHERE `creation_date` >= CURDATE() - INTERVAL 1 DAY 
          AND `creation_date` < CURDATE()
    """
    
    config = get_mysql_config()
    logger.info(f"Connecting to MySQL at {config['host']}")
    
    connection = mysql.connector.connect(**config)
    
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        users = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found {len(users)} new users")
        return users
    finally:
        cursor.close()
        connection.close()


def send_email(users: list[str]) -> None:
    """Send email report with the list of new users."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    subject = f"Daily New Users Report - {yesterday}"
    
    if users:
        body = f"New users registered on {yesterday}:\n\n"
        body += "\n".join(f"  • {user}" for user in users)
        body += f"\n\nTotal: {len(users)} new user(s)"
    else:
        body = f"No new users registered on {yesterday}."
    
    config = get_smtp_config()
    
    msg = MIMEMultipart()
    msg['From'] = config['user']
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP(config['host'], config['port']) as server:
        server.starttls()
        server.login(config['user'], config['password'])
        server.send_message(msg)
    
    logger.info(f"Email sent to {EMAIL_TO}")


def save_to_google_sheets(users: list[str]) -> None:
    """Append the daily report to Google Sheets."""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Use default credentials (Workload Identity in Cloud Run)
    from google.auth import default
    creds, _ = default(scopes=scopes)
    
    client = gspread.authorize(creds)
    
    # Open or create the spreadsheet
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
        logger.info(f"Opened existing spreadsheet: {SPREADSHEET_NAME}")
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(SPREADSHEET_NAME)
        spreadsheet.share(EMAIL_TO, perm_type='user', role='writer')
        logger.info(f"Created new spreadsheet: {SPREADSHEET_NAME}")
    
    sheet = spreadsheet.sheet1
    
    # Add headers if sheet is empty
    if not sheet.get_all_values():
        sheet.append_row(['Date', 'Username', 'Total Count'])
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    if users:
        for i, user in enumerate(users):
            count = len(users) if i == 0 else ''
            sheet.append_row([yesterday, user, count])
    else:
        sheet.append_row([yesterday, '(no new users)', 0])
    
    logger.info(f"Data saved to Google Sheets")


@app.route('/', methods=['POST'])
def run_report():
    """HTTP endpoint triggered by Cloud Scheduler."""
    
    # Verify the request is from Cloud Scheduler (optional but recommended)
    # Cloud Scheduler adds an OIDC token that Cloud Run validates automatically
    
    logger.info("Daily new users report triggered")
    
    try:
        # Step 1: Get new users from MySQL
        users = get_new_users()
        
        # Step 2: Send email report
        send_email(users)
        
        # Step 3: Save to Google Sheets
        save_to_google_sheets(users)
        
        result = {
            'status': 'success',
            'users_count': len(users),
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"Report completed successfully: {len(users)} users")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Report failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

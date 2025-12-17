#!/usr/bin/env python3
"""
Subscriptions Daily Report (Template)
Customize the SQL query for your schema.

Endpoints:
    POST /          - Run report (triggered by Cloud Scheduler)
    POST /run       - Manual trigger
    GET  /health    - Health check
    GET  /status    - Report status and last run info
"""

import os
import sys
from datetime import datetime
from flask import Flask, jsonify, request

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, '/app')

from shared import db, email_utils, sheets, config, logger, yesterday

app = Flask(__name__)

# Report configuration
REPORT_NAME = "Subscriptions"
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', config.sheet_subscriptions)
EMAIL_TO = os.getenv('EMAIL_TO', config.email_to)

# Track last run
_last_run = {
    'timestamp': None,
    'status': None,
    'count': None,
    'error': None
}


def get_subscriptions() -> list[dict]:
    """
    Query MySQL for subscriptions created yesterday.
    
    TODO: Customize this query for your schema.
    """
    query = """
        SELECT 
            u.username,
            s.subscription_type,
            s.created_at
        FROM subscriptions s
        JOIN engine4_users u ON s.user_id = u.user_id
        WHERE s.created_at >= CURDATE() - INTERVAL 1 DAY 
          AND s.created_at < CURDATE()
        ORDER BY s.created_at DESC
    """
    
    results = db.execute_query(query, dictionary=True)
    logger.info(f"Found {len(results)} new subscriptions for {yesterday()}")
    return results


def send_report_email(subscriptions: list[dict]) -> bool:
    """Send email report."""
    date = yesterday()
    subject = f"StageLync {REPORT_NAME} Report - {date}"
    
    if subscriptions:
        body = f"New subscriptions on {date}:\n\n"
        for sub in subscriptions:
            body += f"  • {sub['username']} - {sub['subscription_type']}\n"
        body += f"\nTotal: {len(subscriptions)} new subscription(s)"
    else:
        body = f"No new subscriptions on {date}."
    
    return email_utils.send_email(EMAIL_TO, subject, body)


def save_to_sheets(subscriptions: list[dict]) -> bool:
    """Save report to Google Sheets."""
    date = yesterday()
    headers = ['Date', 'Username', 'Subscription Type', 'Daily Total']
    
    spreadsheet = sheets.get_or_create_spreadsheet(SPREADSHEET_NAME, EMAIL_TO)
    worksheet = spreadsheet.sheet1
    sheets.ensure_headers(worksheet, headers)
    
    if subscriptions:
        rows = []
        for i, sub in enumerate(subscriptions):
            count = len(subscriptions) if i == 0 else ''
            rows.append([date, sub['username'], sub['subscription_type'], count])
        sheets.append_rows(worksheet, rows)
    else:
        sheets.append_row(worksheet, [date, '(no subscriptions)', '-', 0])
    
    logger.info(f"Saved {len(subscriptions)} subscriptions to '{SPREADSHEET_NAME}'")
    return True


def run_report() -> dict:
    """Execute the report and return results."""
    global _last_run
    
    start_time = datetime.now()
    logger.info(f"Starting {REPORT_NAME} report")
    
    try:
        subscriptions = get_subscriptions()
        email_sent = send_report_email(subscriptions)
        sheets_saved = save_to_sheets(subscriptions)
        
        _last_run = {
            'timestamp': start_time.isoformat(),
            'status': 'success',
            'count': len(subscriptions),
            'error': None
        }
        
        return {
            'status': 'success',
            'report': 'subscriptions',
            'date': yesterday(),
            'count': len(subscriptions),
            'email_sent': email_sent,
            'sheets_saved': sheets_saved,
            'duration_ms': int((datetime.now() - start_time).total_seconds() * 1000)
        }
        
    except Exception as e:
        logger.error(f"Report failed: {e}", exc_info=True)
        _last_run = {
            'timestamp': start_time.isoformat(),
            'status': 'error',
            'count': None,
            'error': str(e)
        }
        raise


@app.route('/', methods=['POST'])
def scheduled_run():
    """Main endpoint for Cloud Scheduler."""
    try:
        return jsonify(run_report()), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/run', methods=['POST'])
def manual_run():
    """Manual trigger endpoint."""
    try:
        return jsonify(run_report()), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'report': 'subscriptions'}), 200


@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'report': 'subscriptions',
        'spreadsheet': SPREADSHEET_NAME,
        'last_run': _last_run
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

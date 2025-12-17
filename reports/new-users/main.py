#!/usr/bin/env python3
"""
New Users Daily Report
Queries MySQL for yesterday's new users, sends email, logs to Google Sheets.

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
REPORT_NAME = "New Users"
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', config.sheet_new_users)
EMAIL_TO = os.getenv('EMAIL_TO', config.email_to)

# Track last run
_last_run = {
    'timestamp': None,
    'status': None,
    'count': None,
    'error': None
}


def get_new_users() -> list[str]:
    """Query MySQL for users created yesterday."""
    query = """
        SELECT username 
        FROM `engine4_users` 
        WHERE `creation_date` >= CURDATE() - INTERVAL 1 DAY 
          AND `creation_date` < CURDATE()
    """
    
    results = db.execute_query(query)
    users = [row[0] for row in results]
    logger.info(f"Found {len(users)} new users for {yesterday()}")
    return users


def send_report_email(users: list[str]) -> bool:
    """Send email report."""
    return email_utils.send_report_email(
        report_name=REPORT_NAME,
        date=yesterday(),
        items=users,
        to=EMAIL_TO
    )


def save_to_sheets(users: list[str]) -> bool:
    """Save report to Google Sheets."""
    date = yesterday()
    headers = ['Date', 'Username', 'Daily Total']
    
    def row_formatter(user):
        return [date, user, '']
    
    # For first user, include count
    if users:
        first_user = users[0]
        rest_users = users[1:] if len(users) > 1 else []
        
        spreadsheet = sheets.get_or_create_spreadsheet(SPREADSHEET_NAME, EMAIL_TO)
        worksheet = spreadsheet.sheet1
        sheets.ensure_headers(worksheet, headers)
        
        # First row with count
        sheets.append_row(worksheet, [date, first_user, len(users)])
        
        # Rest of users
        if rest_users:
            rows = [[date, user, ''] for user in rest_users]
            sheets.append_rows(worksheet, rows)
        
        logger.info(f"Saved {len(users)} users to '{SPREADSHEET_NAME}'")
        return True
    else:
        return sheets.save_report_to_sheet(
            spreadsheet_name=SPREADSHEET_NAME,
            date=date,
            items=[],
            headers=headers,
            row_formatter=row_formatter,
            share_with=EMAIL_TO
        )


def run_report() -> dict:
    """Execute the report and return results."""
    global _last_run
    
    start_time = datetime.now()
    logger.info(f"Starting {REPORT_NAME} report")
    
    try:
        # Step 1: Get data
        users = get_new_users()
        
        # Step 2: Send email
        email_sent = send_report_email(users)
        if not email_sent:
            logger.warning("Email sending failed")
        
        # Step 3: Save to sheets
        sheets_saved = save_to_sheets(users)
        if not sheets_saved:
            logger.warning("Google Sheets save failed")
        
        # Update last run
        _last_run = {
            'timestamp': start_time.isoformat(),
            'status': 'success',
            'count': len(users),
            'error': None,
            'email_sent': email_sent,
            'sheets_saved': sheets_saved
        }
        
        logger.info(f"Report completed: {len(users)} users")
        
        return {
            'status': 'success',
            'report': 'new-users',
            'date': yesterday(),
            'count': len(users),
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


# =============================================================================
# Flask Endpoints
# =============================================================================

@app.route('/', methods=['POST'])
def scheduled_run():
    """
    Main endpoint for Cloud Scheduler.
    Triggered automatically at scheduled time.
    """
    logger.info("Report triggered by scheduler")
    
    try:
        result = run_report()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'report': 'new-users',
            'error': str(e)
        }), 500


@app.route('/run', methods=['POST'])
def manual_run():
    """
    Manual trigger endpoint.
    Use this to run the report on-demand.
    
    Example:
        curl -X POST https://SERVICE-URL/run
    """
    logger.info("Report triggered manually")
    
    try:
        result = run_report()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'report': 'new-users',
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({
        'status': 'healthy',
        'report': 'new-users',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """
    Get report status and last run information.
    
    Example:
        curl https://SERVICE-URL/status
    """
    return jsonify({
        'report': 'new-users',
        'spreadsheet': SPREADSHEET_NAME,
        'email_to': EMAIL_TO,
        'last_run': _last_run,
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/test/db', methods=['GET'])
def test_db():
    """Test database connectivity."""
    try:
        success = db.test_connection()
        version = db.execute_scalar("SELECT VERSION()") if success else None
        return jsonify({
            'status': 'success' if success else 'error',
            'mysql_version': version
        }), 200 if success else 500
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

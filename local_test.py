#!/usr/bin/env python3
"""
Local Testing Script for Daily New Users Report
Test MySQL connection, data fetching, and email sending locally.

Usage:
    python local_test.py          # Run all tests
    python local_test.py mysql    # Test MySQL only
    python local_test.py email    # Test email only
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import mysql.connector

# =============================================================================
# CONFIGURATION
# Option 1: Create a .env file (copy .env.example to .env and fill in values)
# Option 2: Edit the values directly below
# =============================================================================

def load_env_file():
    """Load .env file if it exists."""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())
        print("✓ Loaded configuration from .env file\n")

load_env_file()

# MySQL Configuration (reads from .env or uses defaults)
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'your-mysql-host'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER', 'your-mysql-user'),
    'password': os.getenv('MYSQL_PASSWORD', 'your-mysql-password'),
    'database': os.getenv('MYSQL_DATABASE', 'your-database-name'),
}

# SMTP Configuration (reads from .env or uses defaults)
SMTP_CONFIG = {
    'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
    'port': int(os.getenv('SMTP_PORT', '587')),
    'user': os.getenv('SMTP_USER', 'your-email@gmail.com'),
    'password': os.getenv('SMTP_PASSWORD', 'your-app-password'),
}

# Email recipient
EMAIL_TO = os.getenv('EMAIL_TO', 'laci@stagelync.com')


def test_mysql_connection():
    """Test 1: Verify MySQL connection."""
    print("\n" + "="*60)
    print("TEST 1: MySQL Connection")
    print("="*60)
    
    try:
        print(f"Connecting to {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}...")
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        print("✓ Connected successfully!")
        
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        print(f"✓ MySQL version: {version}")
        
        cursor.close()
        connection.close()
        print("✓ Connection closed")
        return True
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def test_fetch_data():
    """Test 2: Fetch data from database."""
    print("\n" + "="*60)
    print("TEST 2: Fetch New Users Data")
    print("="*60)
    
    query = """
        SELECT username 
        FROM `engine4_users` 
        WHERE `creation_date` >= CURDATE() - INTERVAL 1 DAY 
          AND `creation_date` < CURDATE()
    """
    
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = connection.cursor()
        
        print("Executing query for yesterday's new users...")
        cursor.execute(query)
        users = [row[0] for row in cursor.fetchall()]
        
        print(f"✓ Query executed successfully")
        print(f"✓ Found {len(users)} new user(s)")
        
        if users:
            print("\nUsernames found:")
            for user in users[:10]:  # Show first 10
                print(f"  - {user}")
            if len(users) > 10:
                print(f"  ... and {len(users) - 10} more")
        else:
            print("\n(No users registered yesterday)")
        
        cursor.close()
        connection.close()
        return users
        
    except Exception as e:
        print(f"✗ Query failed: {e}")
        return None


def test_send_email(users=None):
    """Test 3: Send test email."""
    print("\n" + "="*60)
    print("TEST 3: Send Email")
    print("="*60)
    
    if users is None:
        users = ['test_user_1', 'test_user_2']  # Dummy data for testing
        print("(Using dummy data since no real users provided)")
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    subject = f"[TEST] Daily New Users Report - {yesterday}"
    
    if users:
        body = f"New users registered on {yesterday}:\n\n"
        body += "\n".join(f"  • {user}" for user in users)
        body += f"\n\nTotal: {len(users)} new user(s)"
    else:
        body = f"No new users registered on {yesterday}."
    
    body += "\n\n---\nThis is a TEST email from local development."
    
    try:
        print(f"Connecting to {SMTP_CONFIG['host']}:{SMTP_CONFIG['port']}...")
        
        msg = MIMEMultipart()
        msg['From'] = SMTP_CONFIG['user']
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as server:
            server.starttls()
            print("✓ TLS connection established")
            
            server.login(SMTP_CONFIG['user'], SMTP_CONFIG['password'])
            print("✓ Login successful")
            
            server.send_message(msg)
            print(f"✓ Email sent to {EMAIL_TO}")
        
        return True
        
    except Exception as e:
        print(f"✗ Email failed: {e}")
        return False


def run_all_tests():
    """Run all tests in sequence."""
    print("\n" + "#"*60)
    print("# LOCAL TESTING - Daily New Users Report")
    print("#"*60)
    
    results = {}
    
    # Test 1: MySQL Connection
    results['mysql_connection'] = test_mysql_connection()
    
    # Test 2: Fetch Data (only if connection works)
    users = None
    if results['mysql_connection']:
        users = test_fetch_data()
        results['fetch_data'] = users is not None
    else:
        results['fetch_data'] = False
        print("\n⚠ Skipping data fetch (MySQL connection failed)")
    
    # Test 3: Send Email
    results['send_email'] = test_send_email(users)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test}: {status}")
    
    all_passed = all(results.values())
    print("\n" + ("All tests passed! Ready for Cloud Run deployment." if all_passed else "Some tests failed. Fix issues before deploying."))
    
    return all_passed


def test_mysql_only():
    """Quick test for MySQL only."""
    test_mysql_connection()
    test_fetch_data()


def test_email_only():
    """Quick test for email only (with dummy data)."""
    test_send_email()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'mysql':
            test_mysql_only()
        elif sys.argv[1] == 'email':
            test_email_only()
        else:
            print("Usage: python local_test.py [mysql|email]")
    else:
        run_all_tests()

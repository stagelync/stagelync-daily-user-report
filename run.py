#!/usr/bin/env python3
"""
StageLync Reports - Local Runner

Run reports directly from your local machine.

Usage:
    python run.py new-users              # Run new users report
    python run.py subscriptions          # Run subscriptions report
    python run.py new-users --dry-run    # Preview without sending email/updating sheets
    python run.py new-users --email-only # Only send email (no sheets update)
    python run.py new-users --sheets-only # Only update sheets (no email)
"""

import sys
import os
import argparse
from datetime import datetime
from urllib.parse import quote, quote_plus

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared import db, email_utils, sheets, config, logger, yesterday


def run_new_users_report(dry_run=False, email_only=False, sheets_only=False):
    """Run the new users report."""
    print(f"\n{'='*60}")
    print(f"  New Users Report - {yesterday()}")
    print(f"{'='*60}\n")
    
    # Step 1: Query database
    print("📊 Querying database...")
    query = """
        SELECT username 
        FROM `engine4_users` 
        WHERE `creation_date` >= CURDATE() - INTERVAL 1 DAY 
          AND `creation_date` < CURDATE()
    """
    
    try:
        results = db.execute_query(query)
        users = [row[0] for row in results]
        print(f"   Found {len(users)} new users")
        user_urls = ["<'https://stagelync.com/profile/" + quote_plus(s) + "'> " + s for s in users]
        
        if users:
            print("\n   Users:")
            for user in users[:10]:
                print(f"   • {user}")
            if len(users) > 10:
                print(f"   ... and {len(users) - 10} more")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False
    
    if dry_run:
        print("\n🔍 DRY RUN - No email sent, no sheets updated")
        return True
    
    # Step 2: Send email
    if not sheets_only:
        print(f"\n📧 Sending email to {config.email_to}...")
        try:
            success = email_utils.send_report_email(
                report_name="New Users",
                date=yesterday(),
                items=user_urls,
                to=config.email_to
            )
            if success:
                print("   ✓ Email sent")
            else:
                print("   ❌ Email failed")
        except Exception as e:
            print(f"   ❌ Email error: {e}")
    
    # Step 3: Update Google Sheets
    if not email_only:
        print(f"\n📊 Updating Google Sheets...")
        try:
            spreadsheet_name = config.sheet_new_users
            # Don't pass share_with when running locally - you already own the sheet
            spreadsheet = sheets.get_or_create_spreadsheet(spreadsheet_name)
            worksheet = spreadsheet.sheet1
            
            headers = ['Date', 'Username', 'Daily Total']
            sheets.ensure_headers(worksheet, headers)
            
            date = yesterday()
            if users:
                # First row with count
                sheets.append_row(worksheet, [date, users[0], len(users)])
                # Rest of users
                if len(users) > 1:
                    rows = [[date, user, ''] for user in users[1:]]
                    sheets.append_rows(worksheet, rows)
            else:
                sheets.append_row(worksheet, [date, '(no new users)', 0])
            
            print(f"   ✓ Updated: {spreadsheet_name}")
            print(f"   📎 {spreadsheet.url}")
        except Exception as e:
            print(f"   ❌ Sheets error: {e}")
    
    print(f"\n{'='*60}")
    print("  ✓ Report complete")
    print(f"{'='*60}\n")
    return True


def run_subscriptions_report(dry_run=False, email_only=False, sheets_only=False):
    """Run the subscriptions report."""
    print(f"\n{'='*60}")
    print(f"  Subscriptions Report - {yesterday()}")
    print(f"{'='*60}\n")
    
    # Step 1: Query database
    print("📊 Querying database...")
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
    
    try:
        results = db.execute_query(query, dictionary=True)
        print(f"   Found {len(results)} new subscriptions")
        
        if results:
            print("\n   Subscriptions:")
            for sub in results[:10]:
                print(f"   • {sub['username']} - {sub['subscription_type']}")
            if len(results) > 10:
                print(f"   ... and {len(results) - 10} more")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        print("   Note: You may need to customize the SQL query for your schema")
        return False
    
    if dry_run:
        print("\n🔍 DRY RUN - No email sent, no sheets updated")
        return True
    
    # Step 2: Send email
    if not sheets_only:
        print(f"\n📧 Sending email to {config.email_to}...")
        try:
            date = yesterday()
            subject = f"StageLync Subscriptions Report - {date}"
            
            if results:
                body = f"New subscriptions on {date}:\n\n"
                for sub in results:
                    body += f"  • {sub['username']} - {sub['subscription_type']}\n"
                body += f"\nTotal: {len(results)} new subscription(s)"
            else:
                body = f"No new subscriptions on {date}."
            
            success = email_utils.send_email(config.email_to, subject, body)
            if success:
                print("   ✓ Email sent")
            else:
                print("   ❌ Email failed")
        except Exception as e:
            print(f"   ❌ Email error: {e}")
    
    # Step 3: Update Google Sheets
    if not email_only:
        print(f"\n📊 Updating Google Sheets...")
        try:
            spreadsheet_name = config.sheet_subscriptions
            # Don't pass share_with when running locally - you already own the sheet
            spreadsheet = sheets.get_or_create_spreadsheet(spreadsheet_name)
            worksheet = spreadsheet.sheet1
            
            headers = ['Date', 'Username', 'Subscription Type', 'Daily Total']
            sheets.ensure_headers(worksheet, headers)
            
            date = yesterday()
            if results:
                rows = []
                for i, sub in enumerate(results):
                    count = len(results) if i == 0 else ''
                    rows.append([date, sub['username'], sub['subscription_type'], count])
                sheets.append_rows(worksheet, rows)
            else:
                sheets.append_row(worksheet, [date, '(no subscriptions)', '-', 0])
            
            print(f"   ✓ Updated: {spreadsheet_name}")
            print(f"   📎 {spreadsheet.url}")
        except Exception as e:
            print(f"   ❌ Sheets error: {e}")
    
    print(f"\n{'='*60}")
    print("  ✓ Report complete")
    print(f"{'='*60}\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Run StageLync reports locally',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py new-users              Run new users report
  python run.py new-users --dry-run    Preview without sending
  python run.py new-users --email-only Only send email
  python run.py subscriptions          Run subscriptions report
        """
    )
    
    parser.add_argument('report', choices=['new-users', 'subscriptions'],
                        help='Report to run')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview only - no email or sheets update')
    parser.add_argument('--email-only', action='store_true',
                        help='Only send email (skip sheets)')
    parser.add_argument('--sheets-only', action='store_true',
                        help='Only update sheets (skip email)')
    
    args = parser.parse_args()
    
    # Validate options
    if args.email_only and args.sheets_only:
        print("Error: Cannot use both --email-only and --sheets-only")
        sys.exit(1)
    
    # Run report
    if args.report == 'new-users':
        success = run_new_users_report(
            dry_run=args.dry_run,
            email_only=args.email_only,
            sheets_only=args.sheets_only
        )
    elif args.report == 'subscriptions':
        success = run_subscriptions_report(
            dry_run=args.dry_run,
            email_only=args.email_only,
            sheets_only=args.sheets_only
        )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

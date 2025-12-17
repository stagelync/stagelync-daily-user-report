#!/usr/bin/env python3
"""
StageLync Reports - Local Testing Suite

Run all tests or individual components to verify configuration.

Usage:
    python -m tests.test_local           # Run all tests
    python -m tests.test_local db        # Test database only
    python -m tests.test_local email     # Test email only
    python -m tests.test_local sheets    # Test Google Sheets only
    python -m tests.test_local config    # Test configuration only
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import config, logger, db, email_utils, sheets, yesterday


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(title: str) -> None:
    """Print section header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{Colors.RESET}\n")


def print_result(name: str, success: bool, details: str = "") -> None:
    """Print test result."""
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if success else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"  {status}  {name}")
    if details:
        print(f"         {Colors.YELLOW}{details}{Colors.RESET}")


def test_config() -> bool:
    """Test configuration loading."""
    print_header("Configuration")
    
    all_passed = True
    
    # Test config values exist
    tests = [
        ("GCP Project ID", config.gcp_project_id, "stagelync-daily-user-reports"),
        ("GCP Region", config.gcp_region, "asia-northeast1"),
        ("MySQL Host", config.mysql_host, None),
        ("MySQL Port", config.mysql_port, 25060),
        ("MySQL User", config.mysql_user, None),
        ("MySQL Database", config.mysql_database, None),
        ("SMTP Host", config.smtp_host, "smtp.gmail.com"),
        ("SMTP Port", config.smtp_port, 587),
        ("SMTP User", config.smtp_user, None),
        ("Email To", config.email_to, "bartosladi@gmail.com"),
    ]
    
    for name, value, expected in tests:
        try:
            if expected is not None:
                success = value == expected
                details = f"= {value}" if success else f"expected {expected}, got {value}"
            else:
                success = value is not None and len(str(value)) > 0
                # Mask sensitive values
                if 'password' in name.lower():
                    details = "= ****" if success else "NOT SET"
                else:
                    details = f"= {value}" if success else "NOT SET"
            
            print_result(name, success, details)
            if not success:
                all_passed = False
        except Exception as e:
            print_result(name, False, str(e))
            all_passed = False
    
    return all_passed


def test_database() -> bool:
    """Test database connectivity and queries."""
    print_header("Database")
    
    all_passed = True
    
    # Test 1: Connection
    try:
        success = db.test_connection()
        print_result("Connection", success)
        if not success:
            all_passed = False
            return all_passed
    except Exception as e:
        print_result("Connection", False, str(e))
        return False
    
    # Test 2: Simple query
    try:
        result = db.execute_scalar("SELECT VERSION()")
        success = result is not None
        print_result("Query (SELECT VERSION())", success, f"= {result}")
        if not success:
            all_passed = False
    except Exception as e:
        print_result("Query (SELECT VERSION())", False, str(e))
        all_passed = False
    
    # Test 3: Check engine4_users table exists
    try:
        result = db.execute_scalar("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'engine4_users'
        """)
        success = result is not None and result > 0
        print_result("Table 'engine4_users' exists", success)
        if not success:
            all_passed = False
    except Exception as e:
        print_result("Table 'engine4_users' exists", False, str(e))
        all_passed = False
    
    # Test 4: Run actual report query
    try:
        users = db.execute_query("""
            SELECT username 
            FROM `engine4_users` 
            WHERE `creation_date` >= CURDATE() - INTERVAL 1 DAY 
              AND `creation_date` < CURDATE()
        """)
        success = True
        print_result("Report query (yesterday's users)", success, f"Found {len(users)} users")
        
        if users:
            print(f"\n  {Colors.BLUE}Sample users:{Colors.RESET}")
            for user in users[:5]:
                print(f"    - {user[0]}")
            if len(users) > 5:
                print(f"    ... and {len(users) - 5} more")
    except Exception as e:
        print_result("Report query", False, str(e))
        all_passed = False
    
    return all_passed


def test_email(send: bool = False) -> bool:
    """Test email configuration and optionally send test email."""
    print_header("Email")
    
    all_passed = True
    
    # Test 1: SMTP Configuration
    tests = [
        ("SMTP Host", config.smtp_host),
        ("SMTP Port", config.smtp_port),
        ("SMTP User", config.smtp_user),
        ("SMTP Password", "****" if config.smtp_password else None),
    ]
    
    for name, value in tests:
        success = value is not None
        print_result(name, success, f"= {value}" if success else "NOT SET")
        if not success:
            all_passed = False
    
    # Test 2: SMTP Connection
    if all_passed:
        try:
            import smtplib
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(config.smtp_user, config.smtp_password)
            print_result("SMTP Connection & Auth", True)
        except Exception as e:
            print_result("SMTP Connection & Auth", False, str(e))
            all_passed = False
    
    # Test 3: Send test email (optional)
    if send and all_passed:
        print(f"\n  {Colors.YELLOW}Sending test email to {config.email_to}...{Colors.RESET}")
        success = email_utils.test_email()
        print_result("Send Test Email", success)
        if not success:
            all_passed = False
    elif not send:
        print(f"\n  {Colors.YELLOW}Tip: Run 'python -m tests.test_local email --send' to send a test email{Colors.RESET}")
    
    return all_passed


def test_sheets(create: bool = False) -> bool:
    """Test Google Sheets configuration."""
    print_header("Google Sheets")
    
    all_passed = True
    
    # Test 1: Check gcloud auth
    print("  Checking authentication...")
    print(f"  {Colors.YELLOW}(Using: gcloud auth application-default login){Colors.RESET}")
    
    # Test 2: Authentication
    try:
        success = sheets.test_sheets()
        print_result("Authentication", success)
        if not success:
            all_passed = False
            print(f"\n  {Colors.YELLOW}Tip: Run 'gcloud auth application-default login' to authenticate{Colors.RESET}")
            return all_passed
    except Exception as e:
        print_result("Authentication", False, str(e))
        print(f"\n  {Colors.YELLOW}Tip: Run 'gcloud auth application-default login' to authenticate{Colors.RESET}")
        all_passed = False
        return all_passed
    
    # Test 3: Create test sheet (optional)
    if create and all_passed:
        try:
            spreadsheet = sheets.get_or_create_spreadsheet(
                "StageLync - Test Sheet",
                share_with=config.email_to
            )
            worksheet = spreadsheet.sheet1
            sheets.ensure_headers(worksheet, ["Date", "Test", "Value"])
            sheets.append_row(worksheet, [yesterday(), "Local Test", "Success"])
            print_result("Create/Update Test Sheet", True, spreadsheet.url)
        except Exception as e:
            print_result("Create/Update Test Sheet", False, str(e))
            all_passed = False
    elif not create:
        print(f"\n  {Colors.YELLOW}Tip: Run 'python -m tests.test_local sheets --create' to create a test sheet{Colors.RESET}")
    
    return all_passed


def run_all_tests() -> bool:
    """Run all tests."""
    print(f"\n{Colors.BOLD}{'#'*60}")
    print(f"#  StageLync Reports - Local Testing Suite")
    print(f"{'#'*60}{Colors.RESET}")
    
    results = {
        'Configuration': test_config(),
        'Database': test_database(),
        'Email': test_email(send=False),
        'Google Sheets': test_sheets(create=False),
    }
    
    # Summary
    print_header("Summary")
    
    all_passed = True
    for name, passed in results.items():
        print_result(name, passed)
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print(f"  {Colors.GREEN}{Colors.BOLD}All tests passed! Ready for deployment.{Colors.RESET}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}Some tests failed. Fix issues before deploying.{Colors.RESET}")
    print()
    
    return all_passed


def main():
    """Main entry point."""
    args = sys.argv[1:]
    
    if not args:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    
    command = args[0].lower()
    flags = args[1:]
    
    if command == 'config':
        success = test_config()
    elif command == 'db' or command == 'database':
        success = test_database()
    elif command == 'email':
        send = '--send' in flags
        success = test_email(send=send)
    elif command == 'sheets':
        create = '--create' in flags
        success = test_sheets(create=create)
    elif command == 'all':
        success = run_all_tests()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

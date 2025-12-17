"""
Google Sheets utilities for StageLync Reports.
Provides spreadsheet creation, reading, and writing helpers.

Authentication:
- Local: Uses `gcloud auth application-default login`
- Cloud Run: Uses default service account credentials
"""

from typing import Any, Optional
import gspread
from gspread import Spreadsheet, Worksheet

from .config import is_cloud_environment
from .logging_config import logger


_client: Optional[gspread.Client] = None


def get_sheets_client() -> gspread.Client:
    """
    Get authenticated gspread client.
    
    Local development: Uses application default credentials from:
        gcloud auth application-default login
    
    Cloud Run: Uses the service's default credentials automatically.
    """
    global _client
    
    if _client is not None:
        return _client
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Use google.auth.default() for both local and cloud
    # - Local: picks up credentials from `gcloud auth application-default login`
    # - Cloud Run: picks up service account credentials automatically
    import google.auth
    creds, project = google.auth.default(scopes=scopes)
    _client = gspread.authorize(creds)
    
    if is_cloud_environment():
        logger.debug("Google Sheets: using Cloud Run default credentials")
    else:
        logger.debug("Google Sheets: using application default credentials")
    
    return _client


def get_or_create_spreadsheet(name: str, share_with: str = None) -> Spreadsheet:
    """
    Get existing spreadsheet or create new one.
    
    Args:
        name: Spreadsheet name
        share_with: Email(s) to share with (comma-separated string or list)
                   Note: Cannot share with the same account you're authenticated as
    
    Returns:
        Spreadsheet object
    """
    client = get_sheets_client()
    
    try:
        spreadsheet = client.open(name)
        logger.debug(f"Opened existing spreadsheet: {name}")
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(name)
        logger.info(f"Created spreadsheet: {name}")
        
        # Share with specified email(s)
        if share_with:
            _share_spreadsheet(spreadsheet, share_with)
    
    return spreadsheet


def _share_spreadsheet(spreadsheet: Spreadsheet, share_with: str) -> None:
    """
    Share spreadsheet with specified email(s).
    Handles errors gracefully (e.g., can't share with yourself).
    
    Args:
        spreadsheet: Spreadsheet to share
        share_with: Email(s) - comma-separated string or list
    """
    # Parse recipients
    if isinstance(share_with, list):
        emails = share_with
    else:
        emails = [e.strip() for e in share_with.split(',') if e.strip()]
    
    for email in emails:
        try:
            spreadsheet.share(email, perm_type='user', role='writer')
            logger.info(f"Shared spreadsheet with {email}")
        except Exception as e:
            # Common errors:
            # - Sharing with yourself (already owner)
            # - Invalid email format
            # - User doesn't exist
            logger.debug(f"Could not share with {email}: {e}")
            # Don't fail - sharing is optional


def get_or_create_worksheet(spreadsheet: Spreadsheet, name: str, rows: int = 1000, cols: int = 26) -> Worksheet:
    """
    Get existing worksheet or create new one.
    
    Args:
        spreadsheet: Parent spreadsheet
        name: Worksheet name
        rows: Number of rows for new worksheet
        cols: Number of columns for new worksheet
    
    Returns:
        Worksheet object
    """
    try:
        worksheet = spreadsheet.worksheet(name)
        logger.debug(f"Opened existing worksheet: {name}")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)
        logger.info(f"Created worksheet: {name}")
    
    return worksheet


def ensure_headers(worksheet: Worksheet, headers: list[str]) -> None:
    """
    Ensure worksheet has headers in first row.
    Only adds if first row is empty.
    """
    existing = worksheet.row_values(1)
    if not existing:
        worksheet.append_row(headers)
        logger.debug(f"Added headers: {headers}")


def append_row(worksheet: Worksheet, row: list[Any]) -> None:
    """
    Append a single row to worksheet.
    """
    worksheet.append_row(row, value_input_option='USER_ENTERED')
    logger.debug(f"Appended row with {len(row)} values")


def append_rows(worksheet: Worksheet, rows: list[list[Any]]) -> None:
    """
    Append multiple rows to worksheet efficiently.
    """
    if not rows:
        return
    
    worksheet.append_rows(rows, value_input_option='USER_ENTERED')
    logger.debug(f"Appended {len(rows)} rows")


def get_all_values(worksheet: Worksheet) -> list[list[str]]:
    """
    Get all values from worksheet.
    """
    return worksheet.get_all_values()


def clear_worksheet(worksheet: Worksheet, keep_headers: bool = True) -> None:
    """
    Clear worksheet content.
    
    Args:
        worksheet: Worksheet to clear
        keep_headers: If True, preserve first row
    """
    if keep_headers:
        headers = worksheet.row_values(1)
        worksheet.clear()
        if headers:
            worksheet.append_row(headers)
    else:
        worksheet.clear()
    
    logger.debug("Worksheet cleared")


def save_report_to_sheet(
    spreadsheet_name: str,
    date: str,
    items: list,
    headers: list[str],
    row_formatter: callable,
    share_with: str = None
) -> bool:
    """
    Save report data to Google Sheet.
    
    Args:
        spreadsheet_name: Name of spreadsheet
        date: Report date
        items: List of items to save
        headers: Column headers
        row_formatter: Function to convert item to row list
        share_with: Email(s) to share with (optional, comma-separated or list)
                   Note: Sharing errors are handled gracefully
    
    Returns:
        True if successful
    
    Usage:
        save_report_to_sheet(
            spreadsheet_name="My Report",
            date="2024-01-15",
            items=["user1", "user2"],
            headers=["Date", "Username"],
            row_formatter=lambda u: [date, u],
            share_with="team@stagelync.com"  # Optional
        )
    """
    try:
        spreadsheet = get_or_create_spreadsheet(spreadsheet_name, share_with)
        worksheet = spreadsheet.sheet1
        
        # Ensure headers exist
        ensure_headers(worksheet, headers)
        
        # Append rows
        if items:
            rows = [row_formatter(item) for item in items]
            append_rows(worksheet, rows)
        else:
            # Add "no data" row
            no_data_row = [date] + ['(no data)'] * (len(headers) - 1)
            append_row(worksheet, no_data_row)
        
        logger.info(f"Saved {len(items)} items to '{spreadsheet_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save to sheet '{spreadsheet_name}': {e}")
        return False


def test_sheets() -> bool:
    """
    Test Google Sheets connectivity.
    
    Returns:
        True if test successful
    """
    try:
        client = get_sheets_client()
        # Try to list spreadsheets (minimal operation to verify auth works)
        client.list_spreadsheet_files()
        logger.info("Google Sheets connection test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Google Sheets connection test: FAILED - {e}")
        return False

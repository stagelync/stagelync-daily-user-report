"""
Google Sheets utilities for StageLync Reports.
Provides spreadsheet creation, reading, and writing helpers.
"""

from typing import Any, Optional
import gspread
from gspread import Spreadsheet, Worksheet

from .config import config, is_cloud_environment
from .logging_config import logger

import google.auth
creds, project = google.auth.default(scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
_client = gspread.authorize(creds)


#_client: Optional[gspread.Client] = None


def get_sheets_client() -> gspread.Client:
    """
    Get authenticated gspread client.
    Uses service account locally, default credentials in Cloud Run.
    """
    global _client
    
    if _client is not None:
        return _client
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    if is_cloud_environment():
        # Use default credentials in Cloud Run
        from google.auth import default
        creds, _ = default(scopes=scopes)
        _client = gspread.authorize(creds)
        logger.debug("Google Sheets: using default credentials")
    else:
        # Use service account locally
        import os
        creds_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_file and os.path.exists(creds_file):
            _client = gspread.service_account(filename=creds_file, scopes=scopes)
            logger.debug(f"Google Sheets: using service account from {creds_file}")
        else:
            # Try application default credentials
            from google.auth import default
            creds, _ = default(scopes=scopes)
            _client = gspread.authorize(creds)
            logger.debug("Google Sheets: using application default credentials")
    
    return _client


def get_or_create_spreadsheet(name: str, share_with: str = None) -> Spreadsheet:
    """
    Get existing spreadsheet or create new one.
    
    Args:
        name: Spreadsheet name
        share_with: Email to share with (optional)
    
    Returns:
        Spreadsheet object
    """
    client = get_sheets_client()
    
    try:
        spreadsheet = client.open(name)
        logger.debug(f"Opened existing spreadsheet: {name}")
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(name)
        if share_with:
            spreadsheet.share(share_with, perm_type='user', role='writer')
            logger.info(f"Created and shared spreadsheet '{name}' with {share_with}")
        else:
            logger.info(f"Created spreadsheet: {name}")
    
    return spreadsheet


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
        share_with: Email to share with
    
    Returns:
        True if successful
    
    Usage:
        save_report_to_sheet(
            spreadsheet_name="My Report",
            date="2024-01-15",
            items=["user1", "user2"],
            headers=["Date", "Username"],
            row_formatter=lambda u: [date, u],
            share_with="laci@stagelync.com"
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
    try:
        client = get_sheets_client()
        client.list_spreadsheet_files()  # Removed: limit=1
        logger.info("Google Sheets connection test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Google Sheets connection test: FAILED - {e}")
        return False

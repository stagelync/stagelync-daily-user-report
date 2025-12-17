"""
StageLync Reports - Shared Utilities

Usage:
    from shared import db, email_utils, sheets, config, logger
    
    # Database
    users = db.execute_query("SELECT * FROM users")
    
    # Email
    email_utils.send_email(to="...", subject="...", body="...")
    
    # Sheets
    sheets.save_report_to_sheet(...)
    
    # Config
    host = config.mysql_host
    
    # Logging
    logger.info("Something happened")
"""

from .config import config, is_cloud_environment
from .logging_config import logger, setup_logging
from . import db
from . import email_utils
from . import sheets

# Date helpers
from datetime import datetime, timedelta


def yesterday() -> str:
    """Get yesterday's date as YYYY-MM-DD string."""
    return (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


def today() -> str:
    """Get today's date as YYYY-MM-DD string."""
    return datetime.now().strftime('%Y-%m-%d')


__all__ = [
    'config',
    'logger',
    'setup_logging',
    'is_cloud_environment',
    'db',
    'email_utils', 
    'sheets',
    'yesterday',
    'today',
]

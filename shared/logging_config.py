"""
Logging configuration for StageLync Reports.
Uses Cloud Logging in production, standard logging locally.
"""

import os
import sys
import logging
from .config import config, is_cloud_environment


def setup_logging(name: str = None) -> logging.Logger:
    """
    Set up logging with Cloud Logging in production.
    
    Args:
        name: Logger name (defaults to 'stagelync')
    
    Returns:
        Configured logger instance
    """
    logger_name = name or 'stagelync'
    logger = logging.getLogger(logger_name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    if is_cloud_environment():
        # Use Cloud Logging in production
        try:
            from google.cloud import logging as cloud_logging
            client = cloud_logging.Client()
            client.setup_logging(log_level=log_level)
            logger.info("Cloud Logging initialized")
        except Exception as e:
            # Fallback to standard logging
            _setup_console_handler(logger, log_level)
            logger.warning(f"Cloud Logging failed, using console: {e}")
    else:
        # Use console logging locally
        _setup_console_handler(logger, log_level)
    
    return logger


def _setup_console_handler(logger: logging.Logger, log_level: int) -> None:
    """Set up console handler with formatting."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Create default logger
logger = setup_logging()

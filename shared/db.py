"""
Database utilities for StageLync Reports.
Provides connection management and query helpers.
"""

from contextlib import contextmanager
from typing import Any, Generator
import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from .config import config
from .logging_config import logger


@contextmanager
def get_connection() -> Generator[MySQLConnection, None, None]:
    """
    Get a MySQL connection as a context manager.
    
    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    connection = None
    try:
        logger.debug(f"Connecting to MySQL at {config.mysql_host}:{config.mysql_port}")
        connection = mysql.connector.connect(
            host=config.mysql_host,
            port=config.mysql_port,
            user=config.mysql_user,
            password=config.mysql_password,
            database=config.mysql_database,
            connection_timeout=30,
            autocommit=True
        )
        logger.debug("MySQL connection established")
        yield connection
    except mysql.connector.Error as e:
        logger.error(f"MySQL connection error: {e}")
        raise
    finally:
        if connection and connection.is_connected():
            connection.close()
            logger.debug("MySQL connection closed")


@contextmanager
def get_cursor(dictionary: bool = False) -> Generator[MySQLCursor, None, None]:
    """
    Get a MySQL cursor as a context manager.
    
    Args:
        dictionary: If True, return rows as dictionaries
    
    Usage:
        with get_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
    """
    with get_connection() as connection:
        cursor = connection.cursor(dictionary=dictionary)
        try:
            yield cursor
        finally:
            cursor.close()


def execute_query(query: str, params: tuple = None, dictionary: bool = False) -> list[Any]:
    """
    Execute a SELECT query and return all results.
    
    Args:
        query: SQL query string
        params: Query parameters (optional)
        dictionary: If True, return rows as dictionaries
    
    Returns:
        List of rows (tuples or dicts)
    
    Usage:
        users = execute_query(
            "SELECT * FROM users WHERE created_at > %s",
            (some_date,),
            dictionary=True
        )
    """
    with get_cursor(dictionary=dictionary) as cursor:
        logger.debug(f"Executing query: {query[:100]}...")
        cursor.execute(query, params)
        results = cursor.fetchall()
        logger.info(f"Query returned {len(results)} rows")
        return results


def execute_query_single(query: str, params: tuple = None, dictionary: bool = False) -> Any:
    """
    Execute a SELECT query and return single result.
    
    Returns:
        Single row or None if no results
    """
    with get_cursor(dictionary=dictionary) as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def execute_scalar(query: str, params: tuple = None) -> Any:
    """
    Execute a query and return single scalar value.
    
    Usage:
        count = execute_scalar("SELECT COUNT(*) FROM users")
    """
    result = execute_query_single(query, params)
    return result[0] if result else None


def test_connection() -> bool:
    """
    Test database connectivity.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            logger.info("Database connection test: SUCCESS")
            return True
    except Exception as e:
        logger.error(f"Database connection test: FAILED - {e}")
        return False

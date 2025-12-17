"""
Email utilities for StageLync Reports.
Provides SMTP email sending with templates.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Union, List
from datetime import datetime

from .config import config
from .logging_config import logger


def _parse_recipients(to: Union[str, List[str]]) -> List[str]:
    """
    Parse recipients from string or list.
    
    Args:
        to: Single email, comma-separated string, or list of emails
    
    Returns:
        List of email addresses
    """
    if isinstance(to, list):
        return [email.strip() for email in to if email.strip()]
    else:
        return [email.strip() for email in to.split(',') if email.strip()]


def send_email(
    to: Union[str, List[str]],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachment_path: Optional[str] = None,
    attachment_name: Optional[str] = None
) -> bool:
    """
    Send an email via SMTP.
    
    Args:
        to: Recipient email(s) - string (comma-separated) or list
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
        attachment_path: Optional file path to attach
        attachment_name: Optional name for the attachment
    
    Returns:
        True if sent successfully, False otherwise
    
    Usage:
        # Single recipient
        send_email(to="laci@stagelync.com", subject="Report", body="...")
        
        # Multiple recipients (comma-separated)
        send_email(to="laci@stagelync.com,team@stagelync.com", subject="Report", body="...")
        
        # Multiple recipients (list)
        send_email(to=["laci@stagelync.com", "team@stagelync.com"], subject="Report", body="...")
    """
    try:
        recipients = _parse_recipients(to)
        
        if not recipients:
            logger.error("No valid recipients provided")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['From'] = config.smtp_user
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        # Attach plain text
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach HTML if provided
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))
        
        # Attach file if provided
        if attachment_path:
            _attach_file(msg, attachment_path, attachment_name)
        
        # Send
        logger.debug(f"Connecting to SMTP server {config.smtp_host}:{config.smtp_port}")
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.send_message(msg)
        
        logger.info(f"Email sent to {', '.join(recipients)}: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def _attach_file(msg: MIMEMultipart, file_path: str, file_name: Optional[str] = None) -> None:
    """Attach a file to the email message."""
    import os
    
    if file_name is None:
        file_name = os.path.basename(file_path)
    
    with open(file_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
        msg.attach(part)


def send_report_email(
    report_name: str,
    date: str,
    items: list,
    item_formatter: callable = None,
    to: Union[str, List[str]] = None
) -> bool:
    """
    Send a standardized report email.
    
    Args:
        report_name: Name of the report (e.g., "New Users")
        date: Report date
        items: List of items to report
        item_formatter: Optional function to format each item
        to: Recipient(s) - string, comma-separated, or list (defaults to config.email_to)
    
    Returns:
        True if sent successfully
    
    Usage:
        # Single recipient
        send_report_email(
            report_name="New Users",
            date="2024-01-15",
            items=["user1", "user2", "user3"]
        )
        
        # Multiple recipients
        send_report_email(
            report_name="New Users",
            date="2024-01-15",
            items=["user1", "user2"],
            to="laci@stagelync.com,team@stagelync.com"
        )
    """
    to = to or config.email_to
    subject = f"StageLync {report_name} Report - {date}"
    
    if items:
        if item_formatter:
            formatted_items = [item_formatter(item) for item in items]
        else:
            formatted_items = [f"  • {item}" for item in items]
        
        body = f"{report_name} for {date}:\n\n"
        body += "\n".join(formatted_items)
        body += f"\n\nTotal: {len(items)}"
    else:
        body = f"No {report_name.lower()} for {date}."
    
    return send_email(to, subject, body)


def test_email() -> bool:
    """
    Send a test email to verify SMTP configuration.
    
    Returns:
        True if test email sent successfully
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return send_email(
        to=config.email_to,
        subject=f"[TEST] StageLync Email Test - {timestamp}",
        body=f"This is a test email sent at {timestamp}.\n\nIf you received this, email is configured correctly."
    )

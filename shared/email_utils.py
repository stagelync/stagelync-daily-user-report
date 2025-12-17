"""
Email utilities for StageLync Reports.
Provides SMTP email sending with templates.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional
from datetime import datetime

from .config import config
from .logging_config import logger


def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachment_path: Optional[str] = None,
    attachment_name: Optional[str] = None
) -> bool:
    """
    Send an email via SMTP.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
        attachment_path: Optional file path to attach
        attachment_name: Optional name for the attachment
    
    Returns:
        True if sent successfully, False otherwise
    
    Usage:
        send_email(
            to="laci@stagelync.com",
            subject="Daily Report",
            body="Here is your report..."
        )
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = config.smtp_user
        msg['To'] = to
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
        
        logger.info(f"Email sent to {to}: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
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
    to: str = None
) -> bool:
    """
    Send a standardized report email.
    
    Args:
        report_name: Name of the report (e.g., "New Users")
        date: Report date
        items: List of items to report
        item_formatter: Optional function to format each item
        to: Recipient (defaults to config.email_to)
    
    Returns:
        True if sent successfully
    
    Usage:
        send_report_email(
            report_name="New Users",
            date="2024-01-15",
            items=["user1", "user2", "user3"],
            item_formatter=lambda u: f"  • {u}"
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

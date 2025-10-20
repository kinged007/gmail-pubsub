"""
Custom email processing logic.

This file contains the main business logic for processing incoming emails.
Modify this file to implement your specific email processing requirements.

The process_email function is called for each new email received.
"""
import os
from typing import Dict, Any
from src.utils.logger import setup_logger
from src.utils.email_utils import get_headers, extract_message_body, extract_attachments
from src.utils.telegram_utils import send_telegram_message, send_email_notification
from src.config import config

import requests

logger = setup_logger(__name__)


def process_email(message: Dict[str, Any]) -> None:
    """
    Process an incoming Gmail message.
    
    This is the main function that gets called for each new email.
    Implement your custom logic here.
    
    Args:
        message: Gmail message object containing all message data
        
    The message object contains:
    - id: Message ID
    - threadId: Thread ID
    - labelIds: List of label IDs
    - snippet: Message snippet
    - payload: Message payload with headers and body
    - sizeEstimate: Estimated size in bytes
    - historyId: History ID
    - internalDate: Internal date timestamp
    """
    try:
        # Extract basic message information
        message_id = message.get('id', 'unknown')
        thread_id = message.get('threadId', 'unknown')
        snippet = message.get('snippet', '')
        labelIds = message.get('labelIds', [])
        
        # Extract headers
        headers = get_headers(message)
        subject = headers.get('subject', 'No Subject')
        sender = headers.get('from', 'Unknown Sender')
        recipient = headers.get('to', 'Unknown Recipient')
        date = headers.get('date', 'Unknown Date')
        logger.info(message)  # Debug log to see message structure
        # Extract message body
        body_text = extract_message_body(message, html_part=True, strip_html=True)
        if not body_text:
            body_text = extract_message_body(message, html_part=False)
        
        # Log the email details
        logger.info("Processing email:")
        logger.info(f"  ID: {message_id}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  From: {sender}")
        logger.info(f"  To: {recipient}")
        logger.info(f"  Date: {date}")
        logger.info(f"  Snippet: {snippet}")
        logger.info(f"  Body length: {len(body_text)} characters")
        logger.info(f"  Body Snippet: {body_text[:400]}")
        
        # TODO: Implement your custom email processing logic here
        # Examples of what you might want to do:
        
        # Send to Telegram (user's custom implementation)

        # result = send_telegram_message(snippet)
        result = send_email_notification(
            subject, 
            sender, 
            snippet, 
            ", ".join(labelIds),
            message_id
        )
        if result['success']:
            logger.info("✓ Telegram message sent successfully")
        else:
            logger.error(f"✗ Failed to send Telegram message: {result['error']}")

        # 1. Filter emails by sender, subject, or content
        # if 'important@example.com' in sender.lower():
        #     # Handle important emails
        #     pass
        
        # 2. Parse specific email formats
        # if 'invoice' in subject.lower():
        #     # Parse invoice emails
        #     pass
        
        # 3. Extract and process attachments
        # attachments = extract_attachments(message)
        # for attachment in attachments:
        #     # Process each attachment
        #     pass
        
        # 4. Send notifications or webhooks
        # # Send to Slack, Discord, webhook endpoints, etc.
        # pass
        
        # 5. Store in database
        # # Save to your database
        # pass
        
        # For now, just log that we processed the email
        logger.info(f"✓ Successfully processed email {message_id}")
        
    except Exception as e:
        logger.error(f"Error processing email {message.get('id', 'unknown')}: {e}")
        # Don't re-raise the exception to avoid breaking the main flow
        # The error is logged and the processing continues




# Test data for development and testing
DUMMY_EMAIL_PAYLOAD = {
    "id": "test_message_123456789",
    "threadId": "test_thread_987654321",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "This is a test email for development purposes. It contains sample content to test your email processing logic.",
    "payload": {
        "partId": "",
        "mimeType": "multipart/alternative",
        "filename": "",
        "headers": [
            {"name": "From", "value": "test.sender@example.com"},
            {"name": "To", "value": "your.email@gmail.com"},
            {"name": "Subject", "value": "Test Email - Development Sample"},
            {"name": "Date", "value": "Mon, 15 Oct 2024 10:30:00 +0000"},
            {"name": "Message-ID", "value": "<test123@example.com>"}
        ],
        "body": {"size": 0},
        "parts": [
            {
                "partId": "0",
                "mimeType": "text/plain",
                "filename": "",
                "headers": [{"name": "Content-Type", "value": "text/plain; charset=UTF-8"}],
                "body": {
                    "size": 156,
                    # Base64 encoded: "Hello!\n\nThis is a test email for development purposes.\n\nYou can modify this dummy payload to match your specific use case.\n\nBest regards,\nTest System"
                    "data": "SGVsbG8hCgpUaGlzIGlzIGEgdGVzdCBlbWFpbCBmb3IgZGV2ZWxvcG1lbnQgcHVycG9zZXMuCgpZb3UgY2FuIG1vZGlmeSB0aGlzIGR1bW15IHBheWxvYWQgdG8gbWF0Y2ggeW91ciBzcGVjaWZpYyB1c2UgY2FzZS4KCkJlc3QgcmVnYXJkcywKVGVzdCBTeXN0ZW0="
                }
            },
            {
                "partId": "1", 
                "mimeType": "text/html",
                "filename": "",
                "headers": [{"name": "Content-Type", "value": "text/html; charset=UTF-8"}],
                "body": {
                    "size": 234,
                    # Base64 encoded: "<html><body><p>Hello!</p><p>This is a <strong>test email</strong> for development purposes.</p><p>You can modify this dummy payload to match your specific use case.</p><p>Best regards,<br>Test System</p></body></html>"
                    "data": "PGh0bWw+PGJvZHk+PHA+SGVsbG8hPC9wPjxwPlRoaXMgaXMgYSA8c3Ryb25nPnRlc3QgZW1haWw8L3N0cm9uZz4gZm9yIGRldmVsb3BtZW50IHB1cnBvc2VzLjwvcD48cD5Zb3UgY2FuIG1vZGlmeSB0aGlzIGR1bW15IHBheWxvYWQgdG8gbWF0Y2ggeW91ciBzcGVjaWZpYyB1c2UgY2FzZS48L3A+PHA+QmVzdCByZWdhcmRzLDxicj5UZXN0IFN5c3RlbTwvcD48L2JvZHk+PC9odG1sPg=="
                }
            }
        ]
    },
    "sizeEstimate": 1234,
    "historyId": "987654321",
    "internalDate": "1697365800000"
}
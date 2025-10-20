"""
Custom email processing logic.

This file contains the main business logic for processing incoming emails.
Modify this file to implement your specific email processing requirements.

The process_email function is called for each new email received.
"""
from typing import Dict, Any
from datetime import datetime
from src.utils.logger import setup_logger
from src.utils.email_utils import get_headers, extract_message_body, extract_attachments
from src.utils.telegram_utils import send_telegram_message, send_email_notification
from src.config import config

from app.utils import parse_date

from src.database import get_database
from app.models import SampleTableModel


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
        # logger.info(message)  # Debug log to see message structure
        
        # Extract message body
        body_text = extract_message_body(message, html_part=True, strip_html=True)
        if not body_text:
            # Getting plain text instead...
            body_text = extract_message_body(message, html_part=False)
            logger.warning("No HTML body found, using plain text for message %s", message_id)
        
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
        try:
            
            db = get_database()
            
            # Check if database is connected
            if not db.is_connected:
                if not db.connect():
                    logger.warning("Database is not connected, cannot save email log")
                    return False

            # Create a new SampleTableModel instance with the email data
            with db.get_session() as session:
                db_commit = SampleTableModel(
                    email_subject=subject,
                    email_id=message_id,
                    email_sender=sender,
                    email_received_at=datetime.utcnow(),
                    email_snippet=snippet,
                )
                
                session.add(db_commit)
                # Session will be committed automatically by the context manager
                
            logger.info(f"✅ Email log saved to database: {subject}")
            return True
            
        except Exception as e:
            # Check if it's a unique constraint error
            logger.error(f"❌ Error saving email log to database: {e}")
            return False
        
        # For now, just log that we processed the email
        logger.info(f"✓ Successfully processed email {message_id}")
        
    except Exception as e:
        logger.error(f"Error processing email {message.get('id', 'unknown')}: {e}")
        # Don't re-raise the exception to avoid breaking the main flow
        # The error is logged and the processing continues


"""Gmail API handler for processing emails and managing authentication."""

import base64
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from src.utils.logger import setup_logger
from app.process_email import process_email
from src.config import config

logger = setup_logger(__name__)


class GmailHandler:
    """Handles Gmail API operations and email processing."""

    def __init__(self, service_account_info: Dict[str, Any]):
        """
        Initialize Gmail handler with appropriate credentials based on account type.

        Args:
            service_account_info: Service account credentials dictionary (for workspace accounts)
        """
        account_type = config.get_gmail_account_type()
        logger.info(f"Initializing Gmail handler for account type: {account_type}")

        # Initialize state management
        self.state_file = Path("gmail_state.json")
        self.service = None

        # Define Gmail scopes
        scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify'
        ]

        if account_type == "oauth":
            # Use OAuth refresh token for personal Gmail
            self.credentials = self._get_oauth_credentials()
            logger.info("Using OAuth credentials for personal Gmail")

        elif account_type == "workspace":
            # Use service account with domain-wide delegation
            delegated_user_email = os.getenv('DELEGATED_USER_EMAIL') or config.config.get('workspace', {}).get('delegated_user_email', '')
            logger.info(f"Using workspace delegation for user: {delegated_user_email}")

            self.credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=scopes,
                subject=delegated_user_email
            )

        else:
            # Fallback to service account (for backward compatibility)
            logger.info("Using service account credentials")
            self.credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=scopes
            )

        self.service: Optional[Resource] = None

    def _get_oauth_credentials(self) -> Credentials:
        """
        Get OAuth credentials from base64-encoded environment variable.

        Returns:
            OAuth credentials object
        """
        # Get base64-encoded token from environment variable
        token_base64 = os.getenv('GMAIL_OAUTH_TOKEN_JSON')
        if not token_base64:
            raise ValueError(
                "GMAIL_OAUTH_TOKEN_JSON environment variable not found. "
                "Please run the OAuth setup process in the init script."
            )

        try:
            # Decode from base64 and parse JSON
            token_json = base64.b64decode(token_base64).decode('utf-8')
            token_data = json.loads(token_json)

            return Credentials.from_authorized_user_info(token_data, scopes=[
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.modify'
            ])

        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"Error parsing OAuth token from environment: {e}")
            raise ValueError(
                f"Invalid OAuth token in GMAIL_OAUTH_TOKEN_JSON environment variable: {e}. "
                "Please run the OAuth setup process again."
            )
    
    def get_service(self) -> Resource:
        """Get or create Gmail API service."""
        if not self.service:
            self.service = build('gmail', 'v1', credentials=self.credentials)
        return self.service

    def get_last_processed_history_id(self) -> Optional[str]:
        """Get the last processed history ID from state file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('last_history_id')
        except Exception as e:
            logger.warning(f"Error reading state file: {e}")
        return None

    def save_last_processed_history_id(self, history_id: str) -> None:
        """Save the last processed history ID to state file."""
        try:
            state = {}
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

            state['last_history_id'] = history_id

            with open(self.state_file, 'w') as f:
                json.dump(state, f)

            logger.info(f"Saved last processed history ID: {history_id}")
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def process_history(self, history_id: str) -> None:
        """
        Process Gmail history to find and handle new messages.

        Args:
            history_id: Gmail history ID from Pub/Sub notification
        """
        try:
            service = self.get_service()

            # Get the last processed history ID
            last_processed_id = self.get_last_processed_history_id()
            logger.info(f"Last processed history ID: {last_processed_id}")
            logger.info(f"Incoming history ID: {history_id}")

            # Convert to integers for comparison
            try:
                incoming_id = int(history_id)
                last_id = int(last_processed_id) if last_processed_id else 0

                if incoming_id <= last_id:
                    logger.info(f"History ID {incoming_id} is not newer than last processed {last_id}, skipping")
                    return

            except (ValueError, TypeError):
                logger.warning(f"Could not compare history IDs as integers, processing anyway")

            # Use the last processed ID as the starting point, or the incoming ID if no previous state
            start_history_id = last_processed_id if last_processed_id else history_id

            # Use the incoming history ID as the end point (this is the latest state from Pub/Sub)
            end_history_id = history_id

            logger.info(f"Processing history from {start_history_id} to {end_history_id}")

            # List history since the starting history ID
            history_response = service.users().history().list(
                userId='me',
                startHistoryId=start_history_id,
                historyTypes=['messageAdded']
            ).execute()

            history_records = history_response.get('history', [])
            logger.info(f"Found {len(history_records)} history records to process")
            print(history_records)
            if not history_records:
                logger.info("No new history records found")
                # Still update the last processed ID to the incoming one
                self.save_last_processed_history_id(history_id)
                return

            messages_processed = 0
            for record in history_records:
                messages_added = record.get('messagesAdded', [])
                for message_added in messages_added:
                    message_id = message_added['message']['id']
                    logger.info(f"Processing new message: {message_id}")

                    # Fetch and process the message
                    message = self.fetch_message(message_id)
                    if message:
                        self.process_message(message)
                        messages_processed += 1

            logger.info(f"Processed {messages_processed} new messages")

            # Save the incoming history ID as the last processed
            self.save_last_processed_history_id(str(history_id))
                        
        except HttpError as e:
            logger.error(f"Gmail API error processing history: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing history: {e}")
    
    def fetch_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a Gmail message by ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Message data or None if error
        """
        try:
            service = self.get_service()
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            # logger.info("Returned Message ID: %s", message.get('id', 'N/A'))
            if not message.get('id', None):
                logger.info(f"Message {message_id} has no ID, skipping")
                return None
            # logger.info(message) # Debug log to see message structure
            # logger.info(f"Fetched message {message_id}")
            return message
            
        except HttpError as e:
            logger.error(f"Gmail API error fetching message {message_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching message {message_id}: {e}")
            return None
    
    def process_message(self, message: Dict[str, Any]) -> None:
        """
        Process a Gmail message using the custom logic.
        
        Args:
            message: Gmail message data
        """
        try:
            # Extract basic message info for logging
            message_id = message.get('id', 'unknown')
            thread_id = message.get('threadId', 'unknown')
            
            # Get headers for subject and sender
            headers = message.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            
            # Apply label filtering if configured
            labelIds = message.get('labelIds', [])
            requestedLabels = config.get_gmail_watch_label_ids()
            if requestedLabels and not any(label in labelIds for label in requestedLabels):
                logger.info(f"Message {message_id} skipped due to label filter")
                return

            logger.info(f"Processing message {message_id}: '{subject}' from {sender} with labels {labelIds}")

            # Call the custom processing function
            process_email(message)
            
            logger.info(f"Successfully processed message {message_id}")
            
        except Exception as e:
            logger.error(f"Error processing message {message.get('id', 'unknown')}: {e}")
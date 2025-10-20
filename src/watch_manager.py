"""Gmail watch subscription manager."""

from typing import Dict, Any, Optional
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from src.utils.logger import setup_logger
from src.config import config
import json
import os
import base64

logger = setup_logger(__name__)


class WatchManager:
    """Manages Gmail watch subscriptions."""
    
    def __init__(self, service_account_info: Dict[str, Any]):
        """
        Initialize watch manager with appropriate credentials based on account type.

        Args:
            service_account_info: Service account credentials dictionary (for workspace accounts)
        """
        account_type = config.get_gmail_account_type()
        logger.info(f"Initializing watch manager for account type: {account_type}")

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
            logger.info("Building Gmail API service...")
            self.service = build('gmail', 'v1', credentials=self.credentials)
            logger.info("Gmail API service built successfully")
        return self.service
    
    def renew_watch(self) -> Dict[str, Any]:
        """
        Renew Gmail watch subscription.

        Returns:
            Watch response with historyId and expiration
        """
        try:
            service = self.get_service()
            project_id = config.get_project_id()
            topic_name = config.get_topic_name()

            # Construct the topic name
            topic_resource = f"projects/{project_id}/topics/{topic_name}"

            logger.info(f"Renewing Gmail watch for topic: {topic_resource}")

            # First, try to stop any existing watch to avoid precondition errors
            try:
                logger.info("Attempting to stop existing watch first")
                service.users().stop(userId='me').execute()
                logger.info("Existing watch stopped successfully")
            except HttpError as stop_error:
                error_details = stop_error.error_details[0] if stop_error.error_details else {}
                error_reason = error_details.get('reason', 'unknown')

                if error_reason == 'failedPrecondition':
                    logger.info("No existing watch to stop (precondition failed) - this is normal")
                else:
                    logger.warning(f"Error stopping existing watch: {stop_error}")
                    logger.warning(f"Error reason: {error_reason}")

            # Get Gmail labels to watch - prefer label IDs if available
            gmail_label_ids = config.get_gmail_watch_label_ids()
            if gmail_label_ids:
                gmail_labels = gmail_label_ids
                logger.info(f"Watching Gmail label IDs: {gmail_labels}")
            else:
                gmail_labels = config.get_gmail_watch_labels()
                logger.info(f"Watching Gmail label names: {gmail_labels}")
                logger.warning("Using label names instead of IDs - consider running deployment validation to convert to IDs")

            # Create watch request
            watch_request = {
                'topicName': topic_resource,
                'labelIds': gmail_labels,
                'labelFilterAction': 'include'
            }

            logger.info("Executing watch request...")
            # Execute watch request
            response = service.users().watch(
                userId='me',
                body=watch_request
            ).execute()
            
            logger.info("Execution complete with response: ")
            logger.info(response)

            history_id = response.get('historyId')
            expiration = response.get('expiration')

            logger.info(f"Watch renewed successfully. History ID: {history_id}, Expiration: {expiration}")

            return {
                'historyId': history_id,
                'expiration': expiration,
                'status': 'success'
            }

        except HttpError as e:
            logger.error(f"Gmail API error renewing watch: {e}")
            error_details = e.error_details[0] if e.error_details else {}
            error_reason = error_details.get('reason', 'unknown')
            logger.error(f"Watch error reason: {error_reason}")
            logger.error(f"Watch error message: {error_details.get('message', 'N/A')}")

            return {
                'error': str(e),
                'error_reason': error_reason,
                'status': 'error'
            }
        except Exception as e:
            logger.error(f"Unexpected error renewing watch: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }
    
    def stop_watch(self) -> Dict[str, Any]:
        """
        Stop the current Gmail watch subscription.
        
        Returns:
            Response indicating success or failure
        """
        try:
            service = self.get_service()
            
            logger.info("Stopping Gmail watch subscription")
            
            service.users().stop(userId='me').execute()
            
            logger.info("Watch stopped successfully")
            
            return {'status': 'success', 'message': 'Watch stopped'}
            
        except HttpError as e:
            logger.error(f"Gmail API error stopping watch: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }
        except Exception as e:
            logger.error(f"Unexpected error stopping watch: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }
    
    def get_watch_status(self) -> Dict[str, Any]:
        """
        Get current Gmail profile information including watch status.

        Returns:
            Profile information with history ID
        """
        try:
            service = self.get_service()

            profile = service.users().getProfile(userId='me').execute()

            return {
                'emailAddress': profile.get('emailAddress'),
                'messagesTotal': profile.get('messagesTotal'),
                'threadsTotal': profile.get('threadsTotal'),
                'historyId': profile.get('historyId'),
                'status': 'success'
            }

        except HttpError as e:
            logger.error(f"Gmail API error getting profile: {e}")
            error_details = e.error_details[0] if e.error_details else {}
            error_reason = error_details.get('reason', 'unknown')
            logger.error(f"Profile error reason: {error_reason}")
            logger.error(f"Profile error message: {error_details.get('message', 'N/A')}")

            return {
                'error': str(e),
                'error_reason': error_reason,
                'status': 'error'
            }
        except Exception as e:
            logger.error(f"Unexpected error getting profile: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }

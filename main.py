"""
Gmail Push Processing API - Main FastAPI Application

This is the main Cloud Run service that handles:
- /email-notify: Pub/Sub push notifications for new emails
- /renew-watch: Gmail watch subscription renewal
- /stop-watch: Stop Gmail watch subscription
- /watch-status: Get current Gmail watch status
- /health: Health check endpoint
"""

import os
import json
import base64
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from google.cloud import secretmanager
from src.gmail_handler import GmailHandler
from src.watch_manager import WatchManager
from src.utils.logger import setup_logger
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logger = setup_logger(__name__)

# Log startup information
logger.info("🚀 Starting Gmail Push Processing API...")
logger.info(f"Python version: {os.sys.version}")
logger.info(f"PORT environment variable: {os.environ.get('PORT', 'NOT_SET')}")
logger.info(f"GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT', 'NOT_SET')}")

# Initialize FastAPI app
app = FastAPI(title="Gmail Push Processing API", version="1.0.0")
logger.info("✅ FastAPI app initialized")

# Global variables for handlers
gmail_handler = None
watch_manager = None


def process_gmail_history_background(history_id: str, email_address: str = None, notification_type: str = "history"):
    """
    Background task to process Gmail history without blocking the client response.

    Args:
        history_id: Gmail history ID to process
        email_address: Email address (for watch notifications)
        notification_type: Type of notification (history, watch_notification)
    """
    try:
        logger.info(f"🔄 Starting background processing of Gmail history ID: {history_id}")
        if email_address:
            logger.info(f"📧 Processing for email address: {email_address}")

        # Ensure handlers are initialized
        get_service_account_info()

        # Process the history
        gmail_handler.process_history(str(history_id))

        logger.info(f"✅ Successfully completed background processing of history ID: {history_id}")

    except Exception as e:
        logger.error(f"❌ Error in background processing of history ID {history_id}: {e}")
        # Note: We don't raise the exception here since this is a background task
        # The client has already received a success response


def get_environment_info():
    """
    Get environment information including env file variables and config file status.

    Returns:
        Dictionary with environment information
    """
    env_info = {
        'config_yaml_exists': Path('config.yaml').exists(),
        'env_file_exists': Path('.env').exists(),
        'env_variables': {}
    }

    # Get environment variables that are commonly used in this project
    important_env_vars = [
        'GOOGLE_CLOUD_PROJECT',
        'GOOGLE_CLOUD_REGION',
        'GOOGLE_SERVICE_ACCOUNT_JSON',
        'CLOUD_RUN_SERVICE_NAME',
        'PUBSUB_TOPIC_NAME',
        'PUBSUB_SUBSCRIPTION_NAME',
        'SERVICE_ACCOUNT_NAME',
        'LOG_LEVEL',
        'PORT'
    ]

    for var in important_env_vars:
        value = os.getenv(var)
        if value:
            # Show only first 6 characters of the value for security
            masked_value = value[:6] + '...' if len(value) > 6 else value
            env_info['env_variables'][var] = masked_value

    return env_info


def get_service_account_info():
    """
    Get service account credentials from Secret Manager or environment.

    Returns:
        Service account info dictionary
    """
    global gmail_handler, watch_manager

    logger.info("🔐 Initializing service account credentials...")

    if gmail_handler is not None:
        logger.info("✅ Service account already initialized")
        return  # Already initialized
    
    try:
        # Try to get from Secret Manager first
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
        if project_id:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = f"projects/{project_id}/secrets/gmail-service-account/versions/latest"
            
            try:
                response = client.access_secret_version(request={"name": secret_name})
                service_account_info = json.loads(response.payload.data.decode('utf-8'))
                logger.info("Loaded service account from Secret Manager")
            except Exception as e:
                logger.info(f"Could not load Service Account from Secret Manager: {e}")
                raise
        else:
            raise Exception("GOOGLE_CLOUD_PROJECT not set")
            
    except Exception:
        # Fallback to environment variable or local file
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if service_account_json:
            # Decode from base64 and parse JSON
            service_account_json = base64.b64decode(service_account_json).decode('utf-8')
            service_account_info = json.loads(service_account_json)

            # Handle double-encoded JSON (if the result is still a string)
            if isinstance(service_account_info, str):
                service_account_info = json.loads(service_account_info)

            logger.info("Loaded service account from environment variable")
        else:
            # Try local file (for development)
            try:
                with open('service-account.json', 'r') as f:
                    service_account_info = json.load(f)
                logger.info("Loaded service account from local file")
            except FileNotFoundError:
                logger.error("No service account credentials found")
                raise Exception("Service account credentials not found")
    
    # Initialize handlers
    gmail_handler = GmailHandler(service_account_info)
    watch_manager = WatchManager(service_account_info)
    logger.info("Initialized Gmail handler and watch manager")


@app.get('/health')
def health():
    """Health check endpoint."""
    logger.info("🏥 Health check endpoint called")

    # Get environment information
    env_info = get_environment_info()

    return {
        'status': 'healthy',
        'service': 'gmail-push-api',
        'version': '1.0.0',
        'environment': env_info
    }


@app.get('/startup')
def startup_check():
    """Startup check endpoint to test service account initialization"""
    logger.info("🚀 Startup check endpoint called")
    try:
        get_service_account_info()
        return {
            'status': 'ready',
            'message': 'Service account initialized successfully',
            'handlers': {
                'gmail_handler': gmail_handler is not None,
                'watch_manager': watch_manager is not None
            }
        }
    except Exception as e:
        logger.error(f"❌ Startup check failed: {e}")
        return {
            'status': 'error',
            'message': f'Service account initialization failed: {str(e)}',
            'handlers': {
                'gmail_handler': gmail_handler is not None,
                'watch_manager': watch_manager is not None
            }
        }


@app.post('/email-notify')
async def email_notify(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Pub/Sub push notifications for new emails.

    Gmail push notifications send message data directly, not historyId.
    The message.data field contains base64-encoded email information.

    Expected payload:
    {
        "message": {
            "data": "base64-encoded-gmail-message-data",
            "messageId": "message-id",
            "publishTime": "timestamp"
        }
    }
    """
    try:
        # Ensure handlers are initialized
        get_service_account_info()

        # Get the Pub/Sub message
        envelope = await request.json()
        if not envelope:
            logger.warning("No JSON payload received")
            raise HTTPException(status_code=400, detail="No JSON payload")

        logger.info(f"Received Pub/Sub envelope: {envelope}")
        pubsub_message = envelope.get('message')
        if not pubsub_message:
            logger.warning("No message in payload")
            raise HTTPException(status_code=400, detail="No message in payload")

        # Get message data and ID
        message_data = pubsub_message.get('data', '')
        message_id = pubsub_message.get('messageId') or pubsub_message.get('message_id')

        if not message_data:
            logger.warning("Empty message data")
            raise HTTPException(status_code=400, detail="Empty message data")

        try:
            logger.info("Decoding Pub/Sub message data")

            # Decode the base64 message data
            decoded_data = base64.b64decode(message_data).decode('utf-8')

            # Try to parse as JSON (Gmail push notifications may send JSON)
            try:
                notification_data = json.loads(decoded_data)
                logger.info(f"Parsed notification data.")

                # Check if this is a Gmail history notification
                if 'historyId' in notification_data:
                    history_id = notification_data.get('historyId')
                    email_address = notification_data.get('emailAddress')

                    if email_address:
                        # This is a watch notification with both emailAddress and historyId
                        # This typically means the watch is active and reporting current state
                        logger.info(f"Received Gmail watch notification for {email_address} with history ID: {history_id}")
                        logger.info("📤 Queuing Gmail history processing in background task")

                        # Queue background processing - don't block the client
                        background_tasks.add_task(
                            process_gmail_history_background,
                            str(history_id),
                            email_address,
                            "watch_notification"
                        )

                        return {
                            'status': 'success',
                            'historyId': history_id,
                            'emailAddress': email_address,
                            'type': 'watch_notification',
                            'processing': 'background'
                        }
                    else:
                        # Traditional Gmail history notification (just historyId)
                        logger.info(f"Received Gmail history notification with history ID: {history_id}")
                        logger.info("📤 Queuing Gmail history processing in background task")

                        # Queue background processing - don't block the client
                        background_tasks.add_task(
                            process_gmail_history_background,
                            str(history_id),
                            None,
                            "history"
                        )

                        return {
                            'status': 'success',
                            'historyId': history_id,
                            'type': 'history',
                            'processing': 'background'
                        }

                elif 'emailAddress' in notification_data:
                    # Gmail watch expiration or profile notification (emailAddress only)
                    email_address = notification_data.get('emailAddress')
                    logger.info(f"Received Gmail profile notification for: {email_address}")
                    return {'status': 'success', 'emailAddress': email_address, 'type': 'profile'}

                else:
                    # Unknown JSON notification format
                    logger.warning(f"Unknown JSON notification format: {notification_data}")
                    return {'status': 'ignored', 'data': notification_data, 'type': 'unknown_json'}

            except json.JSONDecodeError:
                # Not JSON - this might be the actual Gmail message content
                logger.info(f"Message data is not JSON, length: {len(decoded_data)} characters")
                logger.info(f"First 200 characters: {decoded_data[:200]}")

                # This could be the raw email content that Gmail is pushing
                # For now, we'll acknowledge receipt and log it
                logger.warning("Received raw message content from Gmail push notification")

                # TODO: Implement processing of raw Gmail message content
                # This would involve parsing the email format and extracting relevant information

                return {
                    'status': 'received',
                    'messageId': message_id,
                    'type': 'raw_message',
                    'dataLength': len(decoded_data)
                }

        except (UnicodeDecodeError, ValueError) as e:
            logger.error(f"Error decoding message data: {e}")
            raise HTTPException(status_code=400, detail="Invalid base64 message data")

    except Exception as e:
        logger.error(f"Error processing email notification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post('/renew-watch')
def renew_watch():
    """
    Renew Gmail watch subscription.

    This endpoint is called by Cloud Scheduler every 6 days.
    """
    try:
        # Ensure handlers are initialized
        get_service_account_info()

        logger.info("Renewing Gmail watch subscription")

        # Renew the watch
        result = watch_manager.renew_watch()

        if result.get('status') == 'success':
            return result
        else:
            raise HTTPException(status_code=500, detail=result)

    except Exception as e:
        logger.error(f"Error renewing watch: {e}")
        raise HTTPException(status_code=500, detail={'error': 'Internal server error', 'details': str(e)})


@app.get('/watch-status')
def watch_status():
    """
    Get current Gmail watch status and profile information.

    This is a utility endpoint for debugging and monitoring.
    """
    try:
        # Ensure handlers are initialized
        get_service_account_info()

        result = watch_manager.get_watch_status()

        if result.get('status') == 'success':
            return result
        else:
            raise HTTPException(status_code=500, detail=result)

    except Exception as e:
        logger.error(f"Error getting watch status: {e}")
        raise HTTPException(status_code=500, detail={'error': 'Internal server error', 'details': str(e)})


@app.post('/stop-watch')
def stop_watch():
    """
    Stop Gmail watch subscription.

    This endpoint is used to stop the current Gmail watch subscription,
    typically called during project cleanup or reset operations.
    """
    try:
        # Ensure handlers are initialized
        get_service_account_info()

        logger.info("Stopping Gmail watch subscription")

        # Stop the watch
        result = watch_manager.stop_watch()

        if result.get('status') == 'success':
            logger.info("Gmail watch subscription stopped successfully")
            return result
        else:
            logger.error(f"Failed to stop Gmail watch: {result}")
            raise HTTPException(status_code=500, detail=result)

    except Exception as e:
        logger.error(f"Error stopping watch: {e}")
        raise HTTPException(status_code=500, detail={'error': 'Internal server error', 'details': str(e)})


if __name__ == '__main__':
    # For local development
    import uvicorn
    port = int(os.environ.get('PORT', 8080))
    uvicorn.run(app, host='0.0.0.0', port=port)

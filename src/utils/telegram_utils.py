"""
Telegram Bot utility functions for sending notifications.

This module provides utilities for sending messages to Telegram via HTTP requests.
Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file to use these functions.
"""

import os
import requests
import html
from typing import Optional, Dict, Any
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def escape_html_for_telegram(text: str) -> str:
    """
    Escape HTML characters to make text safe for Telegram HTML parsing.

    This function escapes characters that could be interpreted as HTML tags
    by Telegram, making any string safe to send with parse_mode="HTML".

    Args:
        text: The text to escape

    Returns:
        HTML-escaped text safe for Telegram
    """
    if not text:
        return ""

    # Use Python's html.escape to escape HTML characters
    # This will convert < > & " ' to their HTML entities
    escaped = html.escape(text, quote=True)

    return escaped


def send_telegram_message(
    message: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    timeout: int = 10,
    auto_escape_html: bool = True
) -> Dict[str, Any]:
    """
    Send a message to Telegram via HTTP request.

    Args:
        message: The message text to send
        bot_token: Telegram bot token (defaults to TELEGRAM_BOT_TOKEN env var)
        chat_id: Telegram chat ID (defaults to TELEGRAM_CHAT_ID env var)
        parse_mode: Message parse mode ("HTML", "Markdown", or None)
        disable_web_page_preview: Whether to disable link previews
        timeout: Request timeout in seconds
        auto_escape_html: Whether to automatically escape HTML characters when parse_mode="HTML"

    Returns:
        Dictionary with success status and response data
        
    Example:
        # Send a simple message
        result = send_telegram_message("Hello from Gmail Bot!")
        
        # Send formatted message
        result = send_telegram_message(
            "<b>New Email Alert</b>\n"
            "From: sender@example.com\n"
            "Subject: Important Update"
        )
        
        # Check if successful
        if result['success']:
            print("Message sent successfully!")
        else:
            print(f"Failed to send: {result['error']}")
    """
    
    # Get credentials from environment or parameters
    token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN')
    chat = chat_id or os.environ.get('TELEGRAM_CHAT_ID')
    
    # Validate configuration
    if not token or token == 'your-bot-token-here':
        return {
            'success': False,
            'error': 'TELEGRAM_BOT_TOKEN not configured. Get token from @BotFather on Telegram.',
            'message': message
        }
    
    if not chat or chat == 'your-chat-id-here':
        return {
            'success': False,
            'error': 'TELEGRAM_CHAT_ID not configured. Message your bot and visit: https://api.telegram.org/bot<TOKEN>/getUpdates',
            'message': message
        }
    
    # Escape HTML characters if using HTML parse mode and auto-escape is enabled
    if parse_mode and parse_mode.upper() == "HTML" and auto_escape_html:
        message = escape_html_for_telegram(message)

    # Prepare API request
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        'chat_id': chat,
        'text': message,
        'disable_web_page_preview': disable_web_page_preview
    }

    if parse_mode:
        payload['parse_mode'] = parse_mode
    
    try:
        logger.info(f"Sending Telegram message to chat {chat}")
        
        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            logger.info("✅ Telegram message sent successfully")
            return {
                'success': True,
                'message_id': response_data.get('result', {}).get('message_id'),
                'response': response_data,
                'message': message
            }
        else:
            error_msg = response_data.get('description', f'HTTP {response.status_code}')
            logger.error(f"❌ Telegram API error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'response': response_data,
                'message': message
            }
            
    except requests.exceptions.Timeout:
        error_msg = f"Request timeout after {timeout} seconds"
        logger.error(f"❌ Telegram request timeout: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'message': message
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        logger.error(f"❌ Telegram network error: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'message': message
        }
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ Telegram unexpected error: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'message': message
        }


def send_email_notification(
    subject: str,
    sender: str,
    preview: str,
    labels: Optional[list] = None,
    message_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a formatted email notification to Telegram.
    
    Args:
        subject: Email subject line
        sender: Email sender address
        preview: Email content preview (first few lines)
        labels: List of Gmail labels
        message_id: Gmail message ID
        
    Returns:
        Dictionary with success status and response data
        
    Example:
        result = send_email_notification(
            subject="Meeting Tomorrow",
            sender="boss@company.com",
            preview="Don't forget about our team meeting at 2 PM...",
            labels=["INBOX", "IMPORTANT"],
            message_id="abc123"
        )
    """
    
    # Escape user content to prevent HTML parsing errors
    safe_sender = escape_html_for_telegram(sender)
    safe_subject = escape_html_for_telegram(subject)
    safe_preview = escape_html_for_telegram(preview[:500])

    # Format the notification message with escaped content
    message_lines = [
        "📧 <b>New Email Received</b>",
        "",
        f"<b>From:</b> {safe_sender}",
        f"<b>Subject:</b> {safe_subject}",
    ]

    if labels:
        labels_str = ", ".join(labels) if isinstance(labels, list) else str(labels)
        safe_labels = escape_html_for_telegram(labels_str)
        message_lines.append(f"<b>Labels:</b> {safe_labels}")

    if message_id:
        safe_message_id = escape_html_for_telegram(message_id)
        message_lines.append(f"<b>Message ID:</b> <code>{safe_message_id}</code>")

    message_lines.extend([
        "",
        f"<b>Preview:</b>",
        f"<i>{safe_preview}{'...' if len(preview) > 500 else ''}</i>"
    ])

    message = "\n".join(message_lines)

    # Send with auto_escape_html=False to avoid double-escaping since we manually escaped content
    return send_telegram_message(
        message,
        parse_mode="HTML",
        disable_web_page_preview=True,
        auto_escape_html=False
    )


def test_telegram_configuration() -> Dict[str, Any]:
    """
    Test Telegram bot configuration by sending a test message.
    
    Returns:
        Dictionary with test results and configuration status
    """
    
    logger.info("🧪 Testing Telegram bot configuration...")
    
    # Check environment variables
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    config_status = {
        'token_configured': bool(token and token != 'your-bot-token-here'),
        'chat_id_configured': bool(chat_id and chat_id != 'your-chat-id-here'),
        'token': token[:10] + "..." if token and len(token) > 10 else token,
        'chat_id': chat_id
    }
    
    if not config_status['token_configured']:
        return {
            'success': False,
            'error': 'Telegram bot token not configured',
            'config': config_status,
            'instructions': [
                "1. Message @BotFather on Telegram",
                "2. Create a new bot with /newbot",
                "3. Copy the bot token to TELEGRAM_BOT_TOKEN in .env"
            ]
        }
    
    if not config_status['chat_id_configured']:
        return {
            'success': False,
            'error': 'Telegram chat ID not configured',
            'config': config_status,
            'instructions': [
                "1. Message your bot on Telegram",
                f"2. Visit: https://api.telegram.org/bot{token}/getUpdates",
                "3. Copy the chat ID to TELEGRAM_CHAT_ID in .env"
            ]
        }
    
    # Send test message
    test_message = (
        "🤖 <b>Telegram Bot Test</b>\n\n"
        "✅ Configuration successful!\n"
        "Your Gmail Pub/Sub bot can now send notifications to this chat.\n\n"
        f"<i>Test sent at {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )
    
    result = send_telegram_message(test_message)
    result['config'] = config_status
    
    if result['success']:
        logger.info("✅ Telegram configuration test successful")
    else:
        logger.error(f"❌ Telegram configuration test failed: {result['error']}")
    
    return result

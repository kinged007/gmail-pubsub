"""
Email utility functions for Gmail message processing.

This module contains general-purpose utilities for extracting and processing
Gmail message data. These functions are used by the main email processing logic.
"""

import base64
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def _extract_clean_text_from_html(html_content: str) -> str:
    """
    Extract clean text from HTML content using BeautifulSoup.

    This function removes:
    - All HTML tags
    - CSS styles and stylesheets
    - JavaScript code
    - Comments
    - Extra whitespace

    Args:
        html_content: Raw HTML content

    Returns:
        Clean text content with proper spacing
    """
    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements completely
        for script in soup(["script", "style"]):
            script.decompose()

        # Remove comments
        from bs4 import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Get text content
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    except Exception as e:
        logger.warning(f"Error parsing HTML with BeautifulSoup: {e}")
        # Fallback to simple regex if BeautifulSoup fails
        import re
        return re.sub(r'<[^>]+>', '', html_content)


def get_headers(message: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract headers from a Gmail message.
    
    Args:
        message: Gmail message object
        
    Returns:
        Dictionary of header name -> value
    """
    headers = {}
    payload = message.get('payload', {})
    header_list = payload.get('headers', [])
    
    for header in header_list:
        name = header.get('name', '').lower()
        value = header.get('value', '')
        headers[name] = value
    
    return headers


def extract_message_body(message: Dict[str, Any], html_part:bool = False, strip_html:bool = False ) -> str:
    """
    Extract the text body from a Gmail message. By default, returns the text/plain part. If html_part is True, returns the text/html part.
    
    Args:
        message: Gmail message object
        html_part: Whether to extract HTML part or Plain Text (default: False)
        strip_html: Whether to strip HTML tags from the body (default: False)
        
    Returns:
        Extracted text content
    """
    def extract_text_from_part(part: Dict[str, Any], html_part:bool, strip_html:bool ) -> str:
        """Recursively extract text from message parts."""
        text = ""
        mime_type = part.get('mimeType', '')
        
        if mime_type == 'text/plain' and not html_part:
            data = part.get('body', {}).get('data', '')
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    text += decoded
                except Exception as e:
                    logger.warning(f"Error decoding text/plain part: {e}")
        
        elif mime_type == 'text/html' and html_part:
            data = part.get('body', {}).get('data', '')
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if strip_html:
                        # Use BeautifulSoup for proper HTML parsing and text extraction
                        text += _extract_clean_text_from_html(decoded)
                    else:
                        text += decoded
                except Exception as e:
                    logger.warning(f"Error decoding text/html part: {e}")
        
        # Handle multipart messages
        if 'parts' in part:
            for subpart in part['parts']:
                text += extract_text_from_part(subpart, html_part, strip_html)
        
        return text
    
    try:
        payload = message.get('payload', {})
        return extract_text_from_part(payload, html_part, strip_html).strip()
    except Exception as e:
        logger.error(f"Error extracting message body: {e}")
        return ""


def extract_attachments(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract attachment information from a Gmail message.
    
    Args:
        message: Gmail message object
        
    Returns:
        List of attachment dictionaries with filename, mimeType, and attachmentId
    """
    attachments = []
    
    def find_attachments_in_part(part: Dict[str, Any]) -> None:
        """Recursively find attachments in message parts."""
        filename = part.get('filename', '')
        if filename:
            body = part.get('body', {})
            if body.get('attachmentId'):
                attachments.append({
                    'filename': filename,
                    'mimeType': part.get('mimeType', ''),
                    'attachmentId': body.get('attachmentId'),
                    'size': body.get('size', 0)
                })
        
        # Check parts recursively
        if 'parts' in part:
            for subpart in part['parts']:
                find_attachments_in_part(subpart)
    
    try:
        payload = message.get('payload', {})
        find_attachments_in_part(payload)
    except Exception as e:
        logger.error(f"Error extracting attachments: {e}")
    
    return attachments

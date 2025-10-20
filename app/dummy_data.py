
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
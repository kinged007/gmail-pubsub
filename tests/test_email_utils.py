"""Tests for email utility functions."""

import base64
from src.utils.email_utils import get_headers, extract_message_body, extract_attachments


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _msg(headers=None, parts=None, body_data=""):
    headers = headers or []
    payload: dict = {"mimeType": "multipart/alternative", "headers": headers}
    if parts is not None:
        payload["parts"] = parts
    else:
        payload["body"] = {"data": body_data}
    return {"id": "m1", "payload": payload, "labelIds": ["INBOX"]}


def test_get_headers_lowercases_keys():
    msg = {"payload": {"headers": [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]}}
    h = get_headers(msg)
    assert h["subject"] == "Hello"
    assert h["from"] == "a@b.com"


def test_get_headers_empty():
    assert get_headers({"payload": {}}) == {}
    assert get_headers({}) == {}


def test_extract_body_plain_multipart():
    hello = _b64("hello world")
    msg = _msg(parts=[{"mimeType": "text/plain", "body": {"data": hello}}])
    assert extract_message_body(msg) == "hello world"


def test_extract_body_html_stripped():
    html = _b64("<html><body><p>Hello <b>world</b></p></body></html>")
    msg = _msg(parts=[{"mimeType": "text/html", "body": {"data": html}}])
    assert extract_message_body(msg, html_part=True, strip_html=True) == "Hello world"


def test_extract_body_nested_multipart():
    hello = _b64("nested hello")
    msg = _msg(parts=[{"mimeType": "multipart/mixed", "parts": [{"mimeType": "text/plain", "body": {"data": hello}}]}])
    assert extract_message_body(msg) == "nested hello"


def test_extract_body_no_data():
    assert extract_message_body({"payload": {}}) == ""


def test_extract_attachments():
    msg = {
        "payload": {
            "parts": [
                {"filename": "a.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "att1", "size": 100}},
                {"filename": "", "mimeType": "text/plain", "body": {"data": ""}},
            ]
        }
    }
    atts = extract_attachments(msg)
    assert len(atts) == 1
    assert atts[0]["filename"] == "a.pdf"


def test_extract_attachments_nested():
    msg = {
        "payload": {
            "parts": [{"parts": [{"filename": "b.png", "mimeType": "image/png", "body": {"attachmentId": "att2", "size": 42}}]}]
        }
    }
    assert len(extract_attachments(msg)) == 1

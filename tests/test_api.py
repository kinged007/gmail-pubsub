"""Tests for FastAPI endpoints (no real Gmail calls)."""

import base64
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _client():
    # Avoid importing main at top-level twice; lazy import
    import main as m

    return TestClient(m.fapp)


def test_health_returns_ok():
    c = _client()
    r = c.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "database" in data


def test_email_notify_missing_payload():
    c = _client()
    # send invalid json envelope (no message)
    r = c.post("/email-notify", json={})
    assert r.status_code in (400, 500)


def test_email_notify_watch_notification_queued():
    c = _client()
    payload = {"emailAddress": "a@b.com", "historyId": "12345"}
    b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    # Mock service init so we don't need real creds
    with patch("main.get_service_account_info", return_value=None):
        r = c.post("/email-notify", json={"message": {"data": b64, "messageId": "m1"}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["historyId"] == "12345"


def test_config_default_watch_labels():
    from src.config import Config

    cfg = Config(auto_load=False)
    # Without env, should default to INBOX from getenv fallback
    labels = cfg.get_gmail_watch_labels()
    assert isinstance(labels, list)
    assert len(labels) >= 1

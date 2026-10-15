"""Tests for database manager in disabled/memory mode."""

from src.database import DatabaseManager


def test_database_disabled_when_no_url():
    db = DatabaseManager(database_url="")
    assert db.is_connected is False
    assert db.connect() is False
    assert db.health_check()["status"] in ("disabled", "error")


def test_database_sqlite_memory():
    db = DatabaseManager(database_url="sqlite:///:memory:")
    assert db.connect() is True
    assert db.is_connected is True
    hc = db.health_check()
    assert hc["status"] == "healthy"
    db.disconnect()
    assert db.is_connected is False

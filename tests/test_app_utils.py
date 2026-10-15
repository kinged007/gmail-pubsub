"""Tests for app date/hash utilities."""

import datetime
from app.utils import parse_date, create_hash


def test_parse_date_with_cest_converts_to_utc():
    dt = parse_date("20-Oct-2025 11:32 CEST")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.hour == 9  # CEST UTC+2 -> 11:32 CEST = 09:32 UTC
    assert dt.minute == 32


def test_parse_date_no_timezone_assumes_utc():
    dt = parse_date("20-Oct-2025 11:32")
    assert dt is not None
    assert dt.hour == 11


def test_parse_date_invalid_returns_none():
    assert parse_date("not a date") is None
    assert parse_date("") is None


def test_create_hash_deterministic():
    assert create_hash("hello") == create_hash("hello")
    assert create_hash("a") != create_hash("b")
    assert len(create_hash("hello")) == 32

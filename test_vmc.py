import pytest
from datetime import datetime, timezone, timedelta
from vmc import _check_window_expiry

def test_check_window_expiry_missing_opened_at():
    # If opened_at is not present, it should return True
    thread = {}
    assert _check_window_expiry(thread) is True

def test_check_window_expiry_invalid_format():
    # If opened_at cannot be parsed, it should trigger an Exception and return True
    thread = {"opened_at": "invalid-date-format"}
    assert _check_window_expiry(thread) is True

def test_check_window_expiry_under_72_hours():
    # If opened_at is less than 72 hours ago, it should return False
    now = datetime.now(timezone.utc)
    opened_at = now - timedelta(hours=71)
    thread = {"opened_at": opened_at.isoformat()}
    assert _check_window_expiry(thread) is False

def test_check_window_expiry_over_72_hours():
    # If opened_at is more than 72 hours ago, it should return True
    now = datetime.now(timezone.utc)
    opened_at = now - timedelta(hours=73)
    thread = {"opened_at": opened_at.isoformat()}
    assert _check_window_expiry(thread) is True

def test_check_window_expiry_exactly_72_hours():
    # The condition is > 72 hours, so exactly 72 hours should return False
    now = datetime.now(timezone.utc)
    # We add a margin of error for the execution time, as now happens slightly after opened_at
    opened_at = now - timedelta(hours=72) + timedelta(seconds=1)
    thread = {"opened_at": opened_at.isoformat()}
    assert _check_window_expiry(thread) is False

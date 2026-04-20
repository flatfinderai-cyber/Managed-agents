import os
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

# We'll set these before importing to avoid module-level initialization errors
os.environ.setdefault("SUPABASE_URL", "http://localhost:8000")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy_key")

from search_blitz import _now_iso

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Ensure environment variables are isolated for these tests."""
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:8000")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "dummy_key")

def test_now_iso_mocked():
    mock_time = datetime(2023, 10, 25, 12, 34, 56, 789123, tzinfo=timezone.utc)
    with patch("search_blitz.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_time
        mock_datetime.timezone = timezone

        iso_str = _now_iso()

        assert iso_str == "2023-10-25T12:34:56.789123+00:00"
        mock_datetime.now.assert_called_once_with(timezone.utc)

def test_now_iso_parses():
    iso_str = _now_iso()
    dt = datetime.fromisoformat(iso_str)
    assert dt.tzinfo == timezone.utc

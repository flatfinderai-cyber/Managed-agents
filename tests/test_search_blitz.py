import pytest
from fastapi import HTTPException
import os
os.environ["SUPABASE_URL"] = "http://test-url.com"
os.environ["SUPABASE_SERVICE_KEY"] = "a.b.c"
from routes.search_blitz import _require_internal_key

def test_require_internal_key_success(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "super_secret_key")
    # Should not raise an exception
    _require_internal_key("super_secret_key")

def test_require_internal_key_missing_env(monkeypatch):
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        _require_internal_key("any_key")
    assert exc_info.value.status_code == 503
    assert "Internal API key not configured" in exc_info.value.detail

def test_require_internal_key_missing_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "super_secret_key")
    with pytest.raises(HTTPException) as exc_info:
        _require_internal_key(None)
    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.detail

def test_require_internal_key_empty_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "super_secret_key")
    with pytest.raises(HTTPException) as exc_info:
        _require_internal_key("")
    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.detail

def test_require_internal_key_mismatch_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "super_secret_key")
    with pytest.raises(HTTPException) as exc_info:
        _require_internal_key("wrong_key")
    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.detail

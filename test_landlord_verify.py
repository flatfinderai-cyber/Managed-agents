import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from landlord_verify import _get_profile

def test_get_profile_success():
    with patch("landlord_verify.supabase") as mock_supabase:
        mock_execute = MagicMock()
        mock_execute.execute.return_value.data = {"id": "123", "user_id": "user1"}
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value = mock_execute

        result = _get_profile("user1")
        assert result == {"id": "123", "user_id": "user1"}

def test_get_profile_db_error():
    with patch("landlord_verify.supabase") as mock_supabase:
        mock_execute = MagicMock()
        mock_execute.execute.side_effect = Exception("db connection failed")
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value = mock_execute

        with pytest.raises(HTTPException) as exc_info:
            _get_profile("user1")

        assert exc_info.value.status_code == 500
        assert "Failed to load profile: db connection failed" in str(exc_info.value.detail)

def test_get_profile_not_found():
    with patch("landlord_verify.supabase") as mock_supabase:
        mock_execute = MagicMock()
        mock_execute.execute.return_value.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value = mock_execute

        result = _get_profile("user1")
        assert result == {}

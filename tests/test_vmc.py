import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock out supabase before importing the module that calls create_client at the top level
mock_supabase = MagicMock()
sys.modules["supabase"] = mock_supabase

from routes.vmc import _increment_landlord_nonresponse_flag

@patch("routes.vmc._sb")
def test_increment_landlord_nonresponse_success(mock_sb):
    mock_rpc = MagicMock()
    mock_sb.rpc.return_value = mock_rpc
    _increment_landlord_nonresponse_flag("landlord_123")
    mock_sb.rpc.assert_called_once_with("increment_nonresponse", {"p_user_id": "landlord_123"})
    mock_rpc.execute.assert_called_once()

@patch("routes.vmc.print")
@patch("routes.vmc._sb")
def test_increment_landlord_nonresponse_swallows_exception(mock_sb, mock_print):
    mock_rpc = MagicMock()
    mock_rpc.execute.side_effect = Exception("Database connection failed")
    mock_sb.rpc.return_value = mock_rpc
    _increment_landlord_nonresponse_flag("landlord_456")
    mock_sb.rpc.assert_called_once_with("increment_nonresponse", {"p_user_id": "landlord_456"})
    mock_rpc.execute.assert_called_once()
    mock_print.assert_called_once_with("Warning: failed to increment nonresponse for landlord_456: Database connection failed")

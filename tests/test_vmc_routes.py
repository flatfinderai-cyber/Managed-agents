import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure project root is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from routes.vmc import _increment_landlord_nonresponse_flag

@patch('routes.vmc._sb')
def test_increment_landlord_nonresponse_flag_success(mock_sb):
    """Test that the rpc call is made correctly when successful."""
    mock_rpc_query = MagicMock()
    mock_sb.rpc.return_value = mock_rpc_query

    _increment_landlord_nonresponse_flag("landlord_123")

    mock_sb.rpc.assert_called_once_with("increment_nonresponse", {"p_user_id": "landlord_123"})
    mock_rpc_query.execute.assert_called_once()

@patch('routes.vmc._sb')
def test_increment_landlord_nonresponse_flag_failure(mock_sb, capsys):
    """Test that exception is swallowed and a warning is printed when rpc fails."""
    mock_sb.rpc.side_effect = Exception("Supabase connection error")

    # Should not raise an exception
    _increment_landlord_nonresponse_flag("landlord_123")

    captured = capsys.readouterr()
    assert "Warning: failed to increment nonresponse for landlord_123: Supabase connection error" in captured.out

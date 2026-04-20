import pytest
import os

# Set dummy environment variables BEFORE importing routes.vmc
# so that the create_client call during module load doesn't crash.
os.environ["NEXT_PUBLIC_SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "dummy.dummy.dummy"

from unittest.mock import patch, MagicMock
from routes.vmc import _increment_landlord_nonresponse_flag

@patch("routes.vmc._sb")
def test_increment_landlord_nonresponse_success(mock_sb):
    """
    Test that the rpc call is executed successfully when no exception occurs.
    """
    # Setup the mock for _sb.rpc().execute()
    mock_rpc = MagicMock()
    mock_sb.rpc.return_value = mock_rpc

    _increment_landlord_nonresponse_flag("landlord_123")

    mock_sb.rpc.assert_called_once_with("increment_nonresponse", {"p_user_id": "landlord_123"})
    mock_rpc.execute.assert_called_once()

@patch("routes.vmc.print")
@patch("routes.vmc._sb")
def test_increment_landlord_nonresponse_swallows_exception(mock_sb, mock_print):
    """
    Test that if the rpc call raises an exception, the exception is swallowed
    and a warning is printed.
    """
    # Setup the mock to raise an exception
    mock_rpc = MagicMock()
    mock_rpc.execute.side_effect = Exception("Database connection failed")
    mock_sb.rpc.return_value = mock_rpc

    # This should NOT raise an exception
    _increment_landlord_nonresponse_flag("landlord_456")

    mock_sb.rpc.assert_called_once_with("increment_nonresponse", {"p_user_id": "landlord_456"})
    mock_rpc.execute.assert_called_once()
    mock_print.assert_called_once_with("Warning: failed to increment nonresponse for landlord_456: Database connection failed")

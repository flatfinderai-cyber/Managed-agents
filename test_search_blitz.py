import pytest
from unittest.mock import MagicMock, patch

from search_blitz import _fail_order

def test_fail_order_success():
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_update = MagicMock()
    mock_eq = MagicMock()

    mock_supabase.table.return_value = mock_table
    mock_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_eq

    with patch("search_blitz.supabase", mock_supabase), \
         patch("search_blitz._now_iso", return_value="2023-10-10T00:00:00Z"):

         _fail_order("order-123", "Some error message")

         mock_supabase.table.assert_called_once_with("search_blitz_orders")
         mock_table.update.assert_called_once_with({
             "status": "failed",
             "fulfillment_error": "Some error message",
             "completed_at": "2023-10-10T00:00:00Z",
         })
         mock_update.eq.assert_called_once_with("id", "order-123")
         mock_eq.execute.assert_called_once()

def test_fail_order_truncates_long_error():
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_update = MagicMock()
    mock_eq = MagicMock()

    mock_supabase.table.return_value = mock_table
    mock_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_eq

    long_err = "A" * 2500

    with patch("search_blitz.supabase", mock_supabase):
        _fail_order("order-123", long_err)

        args, _ = mock_supabase.table().update.call_args
        assert len(args[0]["fulfillment_error"]) == 2000
        assert args[0]["fulfillment_error"] == "A" * 2000

def test_fail_order_suppresses_exceptions():
    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = Exception("Supabase connection failed")

    with patch("search_blitz.supabase", mock_supabase):
        # This should not raise an exception
        _fail_order("order-123", "Error message")

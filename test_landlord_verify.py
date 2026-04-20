import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

# Mock supabase.create_client before importing landlord_verify
with patch('supabase.create_client', return_value=MagicMock()):
    from landlord_verify import _require_prior_form

def test_require_prior_form_approved():
    """Test that no exception is raised when the prior form is approved."""
    profile = {"form1_kyc_status": "approved"}
    _require_prior_form(profile, "form1_kyc_status", 2)

def test_require_prior_form_missing():
    """Test that a 400 exception is raised when the prior form status is missing."""
    profile = {}
    with pytest.raises(HTTPException) as exc_info:
        _require_prior_form(profile, "form1_kyc_status", 2)

    assert exc_info.value.status_code == 400
    assert "Cannot submit Form 2. Prior form (form1_kyc_status) is not approved." in exc_info.value.detail

def test_require_prior_form_not_approved():
    """Test that a 400 exception is raised when the prior form status is not 'approved'."""
    profile = {"form1_kyc_status": "verified"}
    with pytest.raises(HTTPException) as exc_info:
        _require_prior_form(profile, "form1_kyc_status", 2)

    assert exc_info.value.status_code == 400
    assert "Cannot submit Form 2. Prior form (form1_kyc_status) is not approved." in exc_info.value.detail

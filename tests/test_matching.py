import pytest
import math
from matching import _compliance_score

def test_compliance_score_empty():
    assert math.isclose(_compliance_score({}), 0.0)

def test_compliance_score_kyc_only():
    assert math.isclose(_compliance_score({"kyc_verified": True}), 0.3)

def test_compliance_score_ownership_only():
    assert math.isclose(_compliance_score({"ownership_verified": True}), 0.4)

def test_compliance_score_history_only():
    assert math.isclose(_compliance_score({"history_verified": True}), 0.3)

def test_compliance_score_all_true():
    assert math.isclose(_compliance_score({
        "kyc_verified": True,
        "ownership_verified": True,
        "history_verified": True
    }), 1.0)

def test_compliance_score_false_values():
    assert math.isclose(_compliance_score({
        "kyc_verified": False,
        "ownership_verified": False,
        "history_verified": False
    }), 0.0)

def test_compliance_score_missing_keys():
    assert math.isclose(_compliance_score({"other_key": True}), 0.0)

def test_compliance_score_partial_true():
    assert math.isclose(_compliance_score({
        "kyc_verified": True,
        "ownership_verified": False,
        "history_verified": True
    }), 0.6)

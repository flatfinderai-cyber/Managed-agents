import pytest
from datetime import date
from matching import _months_between

def test_months_between_same_date():
    d1 = date(2023, 1, 1)
    assert _months_between(d1, d1) == 0.0

def test_months_between_approx_one_month():
    d1 = date(2023, 1, 1)
    d2 = date(2023, 1, 31) # 30 days difference
    result = _months_between(d1, d2)
    assert pytest.approx(result, 0.01) == 30 / 30.44

def test_months_between_one_year():
    d1 = date(2023, 1, 1)
    d2 = date(2024, 1, 1) # 365 days
    result = _months_between(d1, d2)
    assert pytest.approx(result, 0.01) == 365 / 30.44
    assert pytest.approx(result, 0.1) == 12.0

def test_months_between_negative_difference():
    d1 = date(2023, 2, 1)
    d2 = date(2023, 1, 1) # -31 days
    result = _months_between(d1, d2)
    assert pytest.approx(result, 0.01) == -31 / 30.44

def test_months_between_leap_year():
    d1 = date(2024, 2, 1)
    d2 = date(2024, 3, 1) # 29 days
    result = _months_between(d1, d2)
    assert pytest.approx(result, 0.01) == 29 / 30.44

def test_months_between_long_period():
    d1 = date(2000, 1, 1)
    d2 = date(2020, 1, 1) # 20 years, 5 leap years = 20 * 365 + 5 = 7305 days
    result = _months_between(d1, d2)
    assert pytest.approx(result, 0.01) == 7305 / 30.44

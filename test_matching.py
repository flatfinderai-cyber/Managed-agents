import pytest
from datetime import date
from matching import _months_between

class TestMonthsBetween:
    def test_same_date(self):
        d1 = date(2023, 1, 1)
        assert _months_between(d1, d1) == 0.0

    def test_positive_difference(self):
        d1 = date(2023, 1, 1)
        d2 = date(2023, 2, 1)
        # 31 days
        assert _months_between(d1, d2) == pytest.approx(31 / 30.44)

    def test_negative_difference(self):
        d1 = date(2023, 2, 1)
        d2 = date(2023, 1, 1)
        # -31 days
        assert _months_between(d1, d2) == pytest.approx(-31 / 30.44)

    def test_leap_year(self):
        d1 = date(2024, 2, 28)
        d2 = date(2024, 2, 29)
        # 1 day
        assert _months_between(d1, d2) == pytest.approx(1 / 30.44)

    def test_one_year_apart(self):
        d1 = date(2023, 1, 1)
        d2 = date(2024, 1, 1)
        # 365 days
        assert _months_between(d1, d2) == pytest.approx(365 / 30.44)

    def test_one_leap_year_apart(self):
        d1 = date(2024, 1, 1)
        d2 = date(2025, 1, 1)
        # 366 days
        assert _months_between(d1, d2) == pytest.approx(366 / 30.44)

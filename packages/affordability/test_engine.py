# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
# Tests: Affordability Engine — TDD

import pytest
from engine import (
    calculate_affordability,
    get_max_rent,
    flag_illegal_screening,
    affordability_summary,
    AFFORDABILITY_UPPER,
    MAX_LEGAL_MULTIPLIER,
)


class TestCalculateAffordability:
    def test_40_percent_exactly(self):
        # $72,000/yr = $6,000/mo. Rent $2,400/mo = exactly 40%
        result = calculate_affordability(72000, 2400)
        assert result.pct_of_income == 40.0
        assert result.is_affordable is True

    def test_33_percent_ideal(self):
        result = calculate_affordability(72000, 1980)
        assert result.pct_of_income == 33.0
        assert result.is_affordable is True

    def test_above_40_not_affordable(self):
        # $60,000/yr = $5,000/mo. Rent $2,200/mo = 44%
        result = calculate_affordability(60000, 2200)
        assert result.pct_of_income == 44.0
        assert result.is_affordable is False

    def test_zero_rent(self):
        result = calculate_affordability(60000, 0)
        assert result.pct_of_income == 0.0
        assert result.is_affordable is True

    def test_max_rent_calculated(self):
        result = calculate_affordability(72000, 2400)
        assert result.max_rent_cad == 2400.0
        assert result.monthly_income == 6000.0


class TestGetMaxRent:
    def test_72k_income(self):
        assert get_max_rent(72000) == 2400.0

    def test_60k_income(self):
        assert get_max_rent(60000) == 2000.0

    def test_50k_income(self):
        assert get_max_rent(50000) == pytest.approx(1666.67, rel=0.01)

    def test_100k_income(self):
        assert get_max_rent(100000) == pytest.approx(3333.33, rel=0.01)


class TestFlagIllegalScreening:
    def test_3x_multiplier_is_illegal(self):
        # Rent $2,400 → agent demands $7,200/mo income = 3x = illegal
        result = flag_illegal_screening(2400, 7200)
        assert result.is_illegal is True
        assert result.multiplier_used == 3.0

    def test_2_5x_is_legal(self):
        # Rent $2,400 → agent demands $6,000/mo income = 2.5x = fine
        result = flag_illegal_screening(2400, 6000)
        assert result.is_illegal is False
        assert result.multiplier_used == 2.5

    def test_exactly_at_threshold_is_legal(self):
        # 2.75x = exactly at limit = legal
        result = flag_illegal_screening(2000, 5500)
        assert result.is_illegal is False

    def test_just_above_threshold_is_illegal(self):
        result = flag_illegal_screening(2000, 5600)
        assert result.is_illegal is True

    def test_zero_rent(self):
        result = flag_illegal_screening(0, 6000)
        assert result.is_illegal is False


class TestAffordabilitySummary:
    def test_affordable_label(self):
        summary = affordability_summary(72000, 2400)
        assert summary["status"] == "affordable"
        assert "40" in summary["label"] or "upper" in summary["label"].lower()

    def test_unaffordable_label(self):
        summary = affordability_summary(40000, 2500)
        assert summary["status"] == "unaffordable"

    def test_excellent_label(self):
        summary = affordability_summary(100000, 2000)
        assert "Excellent" in summary["label"]

    def test_returns_max_rent(self):
        summary = affordability_summary(72000, 2400)
        assert summary["max_affordable_rent_cad"] == 2400.0

    def test_rule_cited(self):
        summary = affordability_summary(72000, 2400)
        assert "33-40%" in summary["rule"]

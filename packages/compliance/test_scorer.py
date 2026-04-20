# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
# Tests: Agent Compliance Scorer — TDD

import pytest
from scorer import (
    score_agent,
    ComplianceInput,
    AgentViolation,
    ViolationType,
    Severity,
    Recommendation,
)


class TestCleanAgent:
    def test_clean_agent_gets_100(self):
        result = score_agent(ComplianceInput(
            violations=[],
            income_multiplier=2.5,
            report_count=0,
            is_multinational=False,
        ))
        assert result.score == 100.0
        assert result.recommendation == Recommendation.SAFE
        assert result.is_blacklisted is False
        assert result.is_flagged is False

    def test_clean_multinational_with_no_issues(self):
        result = score_agent(ComplianceInput(
            violations=[],
            report_count=0,
            is_multinational=True,
        ))
        assert result.score == 100.0
        assert result.recommendation == Recommendation.SAFE


class TestIllegalScreening:
    def test_3x_multiplier_flags_agent(self):
        result = score_agent(ComplianceInput(
            income_multiplier=3.0,
            violations=[],
            report_count=0,
        ))
        assert result.is_flagged is True
        assert result.score < 70
        assert any("gatekeeping" in r.lower() or "multiplier" in r.lower() for r in result.reasons)

    def test_3_5x_multiplier_severe_penalty(self):
        result = score_agent(ComplianceInput(income_multiplier=3.5))
        assert result.score <= 70


class TestUNViolation:
    def test_verified_un_violation_blacklists(self):
        result = score_agent(ComplianceInput(
            violations=[AgentViolation(
                type=ViolationType.UN_HOUSING_RIGHT,
                severity=Severity.CRITICAL,
                verified=True,
                description="Systematic housing rights violation"
            )],
            is_multinational=True,
        ))
        assert result.is_blacklisted is True
        assert result.score < 20
        assert result.recommendation == Recommendation.BLACKLISTED

    def test_unverified_un_violation_flags_not_blacklists(self):
        result = score_agent(ComplianceInput(
            violations=[AgentViolation(
                type=ViolationType.UN_HOUSING_RIGHT,
                severity=Severity.HIGH,
                verified=False,
            )],
        ))
        # Unverified = penalty is reduced, shouldn't auto-blacklist
        assert result.is_blacklisted is False
        assert result.score < 100


class TestPreBlacklisted:
    def test_pre_blacklisted_agent_scores_zero(self):
        # Swiss multinational, MetCap — pre-seeded
        result = score_agent(ComplianceInput(
            is_pre_blacklisted=True,
            violations=[],
            report_count=0,
        ))
        assert result.score == 0.0
        assert result.is_blacklisted is True
        assert result.recommendation == Recommendation.BLACKLISTED


class TestCommunityReports:
    def test_high_report_count_flags(self):
        result = score_agent(ComplianceInput(
            violations=[],
            report_count=15,
            is_multinational=True,
        ))
        assert result.is_flagged is True
        assert result.score < 80

    def test_low_report_count_no_flag(self):
        result = score_agent(ComplianceInput(violations=[], report_count=2))
        assert result.score == 100.0


class TestMultipleViolations:
    def test_combination_blacklists(self):
        # Swiss multinational pattern: illegal screening + UN violation + financial harm
        result = score_agent(ComplianceInput(
            income_multiplier=3.5,
            violations=[
                AgentViolation(ViolationType.UN_HOUSING_RIGHT, Severity.CRITICAL, True),
                AgentViolation(ViolationType.ILLEGAL_SCREENING, Severity.HIGH, True),
                AgentViolation(ViolationType.FINANCIAL_HARM, Severity.HIGH, True),
            ],
            report_count=20,
            is_multinational=True,
        ))
        assert result.is_blacklisted is True
        assert result.score == 0.0
        assert result.recommendation == Recommendation.BLACKLISTED

# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
# Canadian Corporation | Canadian Kind, Scottish Strong
# Unauthorized use, reproduction, or distribution is strictly prohibited.
#
# FlatFinder™ Agent Compliance Scorer
# Protects renters from predatory letting agents and UN housing-rights violators

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

# packages/compliance is run as a flat module (pytest from this dir); resolve sibling `affordability`.
_packages_root = Path(__file__).resolve().parent.parent
if str(_packages_root) not in sys.path:
    sys.path.insert(0, str(_packages_root))

from affordability.engine import MAX_LEGAL_MULTIPLIER


class ViolationType(str, Enum):
    UN_HOUSING_RIGHT = "un_housing_right"
    ILLEGAL_SCREENING = "illegal_screening"
    FRAUD = "fraud"
    DISCRIMINATION = "discrimination"
    FINANCIAL_HARM = "financial_harm"
    HARASSMENT = "harassment"
    RENOVICTION = "renovictions"
    MAINTENANCE_NEGLECT = "maintenance_neglect"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    AVOID = "avoid"
    BLACKLISTED = "blacklisted"


@dataclass
class AgentViolation:
    type: ViolationType
    severity: Severity
    verified: bool
    description: str = ""


@dataclass
class ComplianceInput:
    violations: List[AgentViolation] = field(default_factory=list)
    income_multiplier: Optional[float] = None   # agent's income requirement ratio
    report_count: int = 0
    is_multinational: bool = False
    is_pre_blacklisted: bool = False             # pre-seeded in blacklist


@dataclass
class ComplianceResult:
    score: float                      # 0–100
    is_blacklisted: bool
    is_flagged: bool
    recommendation: Recommendation
    reasons: List[str]
    penalty_breakdown: dict


# How many points each violation type deducts (at full severity, verified)
VIOLATION_PENALTIES = {
    ViolationType.UN_HOUSING_RIGHT:    71,
    ViolationType.ILLEGAL_SCREENING:   30,
    ViolationType.FRAUD:               50,
    ViolationType.DISCRIMINATION:      45,
    ViolationType.FINANCIAL_HARM:      40,
    ViolationType.HARASSMENT:          35,
    ViolationType.RENOVICTION:         30,
    ViolationType.MAINTENANCE_NEGLECT: 25,
}

# Ensure all ViolationType enum values have a default penalty of 20 if missing
for _vt in ViolationType:
    if _vt not in VIOLATION_PENALTIES:
        VIOLATION_PENALTIES[_vt] = 20

SEVERITY_MULTIPLIER = {
    Severity.LOW:      0.25,
    Severity.MEDIUM:   0.50,
    Severity.HIGH:     0.75,
    Severity.CRITICAL: 1.00,
}

# Ensure all Severity enum values have a default multiplier of 0.5 if missing
for _sev in Severity:
    if _sev not in SEVERITY_MULTIPLIER:
        SEVERITY_MULTIPLIER[_sev] = 0.5


def score_agent(input: ComplianceInput) -> ComplianceResult:
    """
    Computes an agent's compliance score (0–100).

    100 = clean record, uses fair screening
      0 = blacklisted, verified UN human rights violations

    Any agent with a UN housing right violation (verified) is auto-blacklisted.
    Any pre-seeded blacklist entry is auto-blacklisted.
    """
    score = 100.0
    reasons: List[str] = []
    penalty_breakdown: dict = {}

    # Pre-seeded blacklist (e.g. the Swiss multinational, MetCap)
    if input.is_pre_blacklisted:
        score = 0.0
        reasons.append("Pre-blacklisted: verified violations on record before launch")
        penalty_breakdown["pre_blacklisted"] = 100

    # Illegal income multiplier
    if input.income_multiplier and input.income_multiplier > MAX_LEGAL_MULTIPLIER:
        penalty = 31
        score -= penalty
        penalty_breakdown["illegal_screening"] = penalty
        reasons.append(
            f"Uses {input.income_multiplier:.1f}x income-to-rent multiplier "
            f"(max legal/ethical: {MAX_LEGAL_MULTIPLIER}x — this is illegal gatekeeping)"
        )

    # Process each violation
    for v in input.violations:
        base_penalty = VIOLATION_PENALTIES[v.type]
        severity_mult = SEVERITY_MULTIPLIER[v.severity]
        verified_mult = 1.0 if v.verified else 0.4

        penalty = base_penalty * severity_mult * verified_mult
        score -= penalty

        key = f"{v.type.value}_{v.severity.value}"
        penalty_breakdown[key] = round(penalty, 1)

        label = f"{v.type.value.replace('_', ' ').title()} ({v.severity.value}"
        label += ", verified" if v.verified else ", unverified"
        label += ")"
        reasons.append(label)

    # Community report volume
    if input.report_count > 10:
        penalty = 21
        score -= penalty
        penalty_breakdown["community_reports"] = penalty
        reasons.append(f"High community report volume ({input.report_count} reports)")
    elif input.report_count > 4:
        penalty = 10
        score -= penalty
        penalty_breakdown["community_reports"] = penalty
        reasons.append(f"Multiple community reports ({input.report_count})")

    # Multinational with issues = extra scrutiny
    if input.is_multinational and score < 70:
        penalty = 10
        score -= penalty
        penalty_breakdown["multinational_risk"] = penalty
        reasons.append("Multinational agency with documented compliance issues — systemic risk")

    score = max(0.0, round(score, 1))

    # Auto-blacklist conditions
    has_verified_un_violation = any(
        v.type == ViolationType.UN_HOUSING_RIGHT and v.verified
        for v in input.violations
    )
    is_blacklisted = (
        input.is_pre_blacklisted
        or has_verified_un_violation
        or score < 20
    )

    is_flagged = not is_blacklisted and (score < 70 or len(reasons) > 0)

    if is_blacklisted:
        recommendation = Recommendation.BLACKLISTED
    elif score < 50:
        recommendation = Recommendation.AVOID
    elif score < 70:
        recommendation = Recommendation.CAUTION
    else:
        recommendation = Recommendation.SAFE

    return ComplianceResult(
        score=score,
        is_blacklisted=is_blacklisted,
        is_flagged=is_flagged,
        recommendation=recommendation,
        reasons=reasons,
        penalty_breakdown=penalty_breakdown,
    )

# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
# Canadian Corporation | Canadian Kind, Scottish Strong
# Unauthorized use, reproduction, or distribution is strictly prohibited.
#
# FlatFinder™ Affordability Engine
# Economist-backed 33-40% income rule — replaces illegal 3x rent multiplier

from dataclasses import dataclass

# The economist-backed thresholds
AFFORDABILITY_LOWER = 0.33   # 33% — ideal
AFFORDABILITY_UPPER = 0.40   # 40% — maximum safe threshold
MAX_LEGAL_MULTIPLIER = 2.75  # income-to-rent ratio above this = predatory screening
                              # (3x = illegal gatekeeping. 2.75x = generous but fair.)


@dataclass
class AffordabilityResult:
    pct_of_income: float         # e.g. 38.5 means rent = 38.5% of monthly income
    is_affordable: bool
    max_rent_cad: float          # maximum rent at 40% threshold
    monthly_income: float


@dataclass
class ScreeningFlagResult:
    is_illegal: bool
    multiplier_used: float
    legal_max_multiplier: float
    explanation: str


def calculate_affordability(annual_income: float, monthly_rent: float) -> AffordabilityResult:
    """
    Returns what percentage of monthly income goes to rent.
    Uses economist-backed 33-40% standard (not the illegal 3x multiplier).

    Example:
        $72,000/yr = $6,000/mo income
        $2,400/mo rent = 40% → affordable (at the upper limit)
        $2,700/mo rent = 45% → not affordable
    """
    monthly_income = annual_income / 12
    if monthly_income == 0:
        return AffordabilityResult(
            pct_of_income=0.0,
            is_affordable=True,
            max_rent_cad=0.0,
            monthly_income=0.0
        )

    pct = round((monthly_rent / monthly_income) * 100, 2)
    max_rent = round(monthly_income * AFFORDABILITY_UPPER, 2)

    return AffordabilityResult(
        pct_of_income=pct,
        is_affordable=pct <= (AFFORDABILITY_UPPER * 100),
        max_rent_cad=max_rent,
        monthly_income=round(monthly_income, 2)
    )


def get_max_rent(annual_income: float) -> float:
    """
    Returns the maximum monthly rent a person can afford at the 40% threshold.

    Example: $72,000/yr → $2,400/mo max rent
    """
    return round((annual_income / 12) * AFFORDABILITY_UPPER, 2)


def flag_illegal_screening(monthly_rent: float, required_monthly_income: float) -> ScreeningFlagResult:
    """
    Returns True if an agent's income requirement is predatory.

    The 3x rent multiplier that gatekeeping agents use demands you earn
    3x your monthly rent — e.g. $2,400 rent → must earn $7,200/mo = $86,400/yr.
    But the 40% rule says $2,400/mo rent is affordable at $6,000/mo ($72,000/yr).
    The 3x rule demands 20% more income than necessary. It is mathematical discrimination.

    This function flags any multiplier above 2.75x as predatory.
    """
    if monthly_rent == 0:
        return ScreeningFlagResult(
            is_illegal=False,
            multiplier_used=0.0,
            legal_max_multiplier=MAX_LEGAL_MULTIPLIER,
            explanation="No rent specified."
        )

    multiplier = required_monthly_income / monthly_rent
    is_illegal = multiplier > MAX_LEGAL_MULTIPLIER

    explanation = (
        f"Agent demands {multiplier:.1f}x monthly rent in income. "
        f"Maximum legal/ethical threshold: {MAX_LEGAL_MULTIPLIER}x. "
        + ("⚠️ ILLEGAL GATEKEEPING — this discriminates against renters who can afford the rent." if is_illegal
           else "✓ Within acceptable range.")
    )

    return ScreeningFlagResult(
        is_illegal=is_illegal,
        multiplier_used=round(multiplier, 2),
        legal_max_multiplier=MAX_LEGAL_MULTIPLIER,
        explanation=explanation
    )


def affordability_summary(annual_income: float, monthly_rent: float) -> dict:
    """
    Full affordability summary — used by the API and Benny chat.
    Returns a dict ready for JSON serialization.
    """
    result = calculate_affordability(annual_income, monthly_rent)
    max_rent = get_max_rent(annual_income)

    status = "affordable" if result.is_affordable else "unaffordable"
    if result.pct_of_income <= 33:
        label = "Excellent — well within your budget"
    elif result.pct_of_income <= 40:
        label = "Affordable — at the upper limit"
    elif result.pct_of_income <= 50:
        label = "Stretched — above recommended threshold"
    else:
        label = "Unaffordable — significant financial risk"

    return {
        "status": status,
        "label": label,
        "pct_of_income": result.pct_of_income,
        "monthly_income_cad": result.monthly_income,
        "monthly_rent_cad": monthly_rent,
        "max_affordable_rent_cad": max_rent,
        "annual_income_cad": annual_income,
        "rule": "33-40% economist-backed affordability standard (FlatFinder™)",
    }

# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™

from fastapi import APIRouter
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages/affordability'))

from engine import affordability_summary, flag_illegal_screening, get_max_rent

router = APIRouter()


class AffordabilityRequest(BaseModel):
    annual_income: float
    monthly_rent: float


class ScreeningCheckRequest(BaseModel):
    monthly_rent: float
    required_monthly_income: float


@router.post("/check")
async def check_affordability(req: AffordabilityRequest):
    """
    Check if a listing is affordable using the 33-40% economist-backed rule.
    Returns full summary including max rent, percentage, and label.
    """
    return affordability_summary(req.annual_income, req.monthly_rent)


@router.post("/flag-screening")
async def flag_screening(req: ScreeningCheckRequest):
    """
    Check if an agent's income requirement is illegal (above 2.75x monthly rent).
    The 3x multiplier used by gatekeeping agents has no legal or ethical basis.
    """
    result = flag_illegal_screening(req.monthly_rent, req.required_monthly_income)
    return {
        "is_illegal": result.is_illegal,
        "multiplier_used": result.multiplier_used,
        "legal_max_multiplier": result.legal_max_multiplier,
        "explanation": result.explanation,
    }


@router.get("/max-rent")
async def max_rent(annual_income: float):
    """Returns the maximum monthly rent affordable at 40% of income."""
    return {
        "annual_income_cad": annual_income,
        "max_monthly_rent_cad": get_max_rent(annual_income),
        "rule": "40% of gross monthly income (economist-backed standard)",
    }

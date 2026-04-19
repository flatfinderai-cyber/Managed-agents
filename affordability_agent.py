# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
#
# Agent 2: Affordability Algorithm Agent
# Wraps the existing 33-40% engine with a Claude tool-use loop.
# Answers tenant questions about affordability, flags illegal screening,
# calculates match scores, and explains the economist-backed rule.

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow importing from packages/affordability
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.affordability.engine import (
    affordability_summary,
    calculate_affordability,
    flag_illegal_screening,
    get_max_rent,
    AFFORDABILITY_LOWER,
    AFFORDABILITY_UPPER,
    MAX_LEGAL_MULTIPLIER,
)

from .base_agent import BaseAgent

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are the FlatFinder™ Affordability Algorithm Agent.

FlatFinder™ is a Canadian anti-gatekeeping rental platform founded by Lila Alexandra Olufemi Inglis Abegunrin.
Our core innovation: the economist-backed 33-40% income affordability rule replaces the discriminatory
3× rent multiplier used by predatory letting agents.

Your mandate:
1. Answer any tenant or landlord question about housing affordability.
2. Calculate whether a specific income / rent combination is affordable.
3. Flag letting agents whose screening requirements exceed 2.75× monthly rent.
4. Recommend the maximum safe rent for a given income.
5. Explain the economic reasoning behind the 33-40% rule in plain English.
6. Score how well a listing matches a tenant's budget.

You ALWAYS use the tools provided — never guess at numbers. Run the calculations first, then explain.
Use British/Canadian English. Never use Americanised emotional language.

Key facts to communicate clearly:
- The 3× rule demands you earn $86,400/yr to rent a $2,400/mo flat. The 40% rule says $72,000/yr
  is sufficient. The 3× rule is mathematical discrimination, not a legal requirement in Canada.
- 33% is the ideal housing cost ratio (economists' standard).
- 40% is the maximum safe threshold — anything above is financially dangerous.
- Savings of 6-12 months rent are a valid alternative qualification method.
"""


class AffordabilityAgent(BaseAgent):
    """
    Claude agent that answers affordability questions using the FlatFinder™ engine.
    """

    @property
    def system_prompt(self) -> str:
        return _SYSTEM

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "name": "calculate_affordability",
                "description": (
                    "Calculate what percentage of a tenant's monthly income goes to rent. "
                    "Returns is_affordable (True if ≤ 40%), pct_of_income, max_rent_cad."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "annual_income": {
                            "type": "number",
                            "description": "Gross annual income in CAD (or relevant currency).",
                        },
                        "monthly_rent": {
                            "type": "number",
                            "description": "Monthly rent in CAD.",
                        },
                    },
                    "required": ["annual_income", "monthly_rent"],
                },
            },
            {
                "name": "get_max_rent",
                "description": (
                    "Returns the maximum monthly rent a person can safely afford "
                    "at the 40% income threshold."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "annual_income": {
                            "type": "number",
                            "description": "Gross annual income in CAD.",
                        },
                    },
                    "required": ["annual_income"],
                },
            },
            {
                "name": "affordability_summary",
                "description": (
                    "Full affordability summary for a given income + rent pair. "
                    "Returns status label, pct_of_income, max_affordable_rent, and a plain-English label."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "annual_income": {"type": "number"},
                        "monthly_rent": {"type": "number"},
                    },
                    "required": ["annual_income", "monthly_rent"],
                },
            },
            {
                "name": "flag_illegal_screening",
                "description": (
                    "Check whether a letting agent's income requirement is predatory. "
                    "Returns is_illegal, multiplier_used, and a plain-English explanation."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "monthly_rent": {
                            "type": "number",
                            "description": "Listed monthly rent in CAD.",
                        },
                        "required_monthly_income": {
                            "type": "number",
                            "description": "Income the agent claims the tenant must earn monthly.",
                        },
                    },
                    "required": ["monthly_rent", "required_monthly_income"],
                },
            },
            {
                "name": "batch_affordability_check",
                "description": (
                    "Check affordability for a list of listings against a single income. "
                    "Returns each listing annotated with its affordability result."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "annual_income": {"type": "number"},
                        "listings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "monthly_rent": {"type": "number"},
                                },
                                "required": ["monthly_rent"],
                            },
                            "description": "List of listings with their monthly_rent.",
                        },
                    },
                    "required": ["annual_income", "listings"],
                },
            },
            {
                "name": "get_rule_explanation",
                "description": (
                    "Return a comprehensive plain-English explanation of the 33-40% rule "
                    "vs the 3× multiplier, with numbers. Use for Benny chat responses."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "example_rent": {
                            "type": "number",
                            "description": "Monthly rent to use in the concrete example (optional).",
                            "default": 2400,
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "savings_qualification",
                "description": (
                    "Calculate whether a tenant qualifies via the savings route "
                    "(6 months rent in savings = acceptable alternative to income requirement)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "monthly_rent": {"type": "number"},
                        "savings_cad": {"type": "number"},
                    },
                    "required": ["monthly_rent", "savings_cad"],
                },
            },
        ]

    # ── Tool implementations ──────────────────────────────────────────────────

    def execute_tool(self, name: str, tool_input: dict) -> Any:
        dispatch = {
            "calculate_affordability":  self._calculate_affordability,
            "get_max_rent":             self._get_max_rent,
            "affordability_summary":    self._affordability_summary,
            "flag_illegal_screening":   self._flag_illegal_screening,
            "batch_affordability_check": self._batch_affordability_check,
            "get_rule_explanation":     self._get_rule_explanation,
            "savings_qualification":    self._savings_qualification,
        }
        fn = dispatch.get(name)
        if not fn:
            raise ValueError(f"Unknown tool: {name}")
        return fn(tool_input)

    def _calculate_affordability(self, args: dict) -> dict:
        result = calculate_affordability(
            annual_income=float(args["annual_income"]),
            monthly_rent=float(args["monthly_rent"]),
        )
        return {
            "pct_of_income": result.pct_of_income,
            "is_affordable": result.is_affordable,
            "max_rent_cad": result.max_rent_cad,
            "monthly_income_cad": result.monthly_income,
            "threshold_used": f"{AFFORDABILITY_UPPER * 100:.0f}%",
        }

    def _get_max_rent(self, args: dict) -> dict:
        max_rent = get_max_rent(float(args["annual_income"]))
        monthly_income = round(float(args["annual_income"]) / 12, 2)
        return {
            "annual_income_cad": args["annual_income"],
            "monthly_income_cad": monthly_income,
            "max_monthly_rent_cad": max_rent,
            "at_33pct": round(monthly_income * AFFORDABILITY_LOWER, 2),
            "at_40pct": max_rent,
        }

    def _affordability_summary(self, args: dict) -> dict:
        return affordability_summary(
            annual_income=float(args["annual_income"]),
            monthly_rent=float(args["monthly_rent"]),
        )

    def _flag_illegal_screening(self, args: dict) -> dict:
        result = flag_illegal_screening(
            monthly_rent=float(args["monthly_rent"]),
            required_monthly_income=float(args["required_monthly_income"]),
        )
        return {
            "is_illegal": result.is_illegal,
            "multiplier_used": result.multiplier_used,
            "legal_max_multiplier": result.legal_max_multiplier,
            "explanation": result.explanation,
            "three_x_equivalent_income": round(float(args["monthly_rent"]) * 3, 2),
            "flatfinder_required_income": round(
                float(args["monthly_rent"]) / AFFORDABILITY_UPPER, 2
            ),
        }

    def _batch_affordability_check(self, args: dict) -> dict:
        annual_income = float(args["annual_income"])
        results = []
        for listing in args["listings"]:
            rent = float(listing["monthly_rent"])
            r = calculate_affordability(annual_income, rent)
            results.append({
                "id": listing.get("id", ""),
                "title": listing.get("title", ""),
                "monthly_rent": rent,
                "pct_of_income": r.pct_of_income,
                "is_affordable": r.is_affordable,
            })
        affordable = [r for r in results if r["is_affordable"]]
        return {
            "annual_income": annual_income,
            "total_checked": len(results),
            "affordable_count": len(affordable),
            "listings": results,
        }

    def _get_rule_explanation(self, args: dict) -> dict:
        rent = float(args.get("example_rent", 2400))
        income_40 = round(rent / AFFORDABILITY_UPPER, 2)
        income_3x = round(rent * 3, 2)
        annual_40 = round(income_40 * 12, 2)
        annual_3x = round(income_3x * 12, 2)
        surplus_monthly = round(income_3x - income_40, 2)
        surplus_pct = round(((income_3x - income_40) / income_40) * 100, 1)
        return {
            "example_rent_cad": rent,
            "rule_33_40_pct": {
                "required_monthly_income": income_40,
                "required_annual_income": annual_40,
                "explanation": (
                    f"At the 40% threshold, a tenant earning ${income_40:,.2f}/mo "
                    f"(${annual_40:,.2f}/yr) can afford ${rent:,.2f}/mo rent."
                ),
            },
            "three_x_multiplier": {
                "required_monthly_income": income_3x,
                "required_annual_income": annual_3x,
                "explanation": (
                    f"The 3× rule demands ${income_3x:,.2f}/mo (${annual_3x:,.2f}/yr) "
                    f"for the same ${rent:,.2f}/mo flat."
                ),
            },
            "gatekeeping_gap": {
                "excess_monthly_income_demanded": surplus_monthly,
                "excess_pct": f"{surplus_pct}% more income demanded than needed",
                "verdict": (
                    "The 3× rule is mathematical gatekeeping — it discriminates against tenants "
                    "who can genuinely afford the rent by demanding 20%+ more income than necessary."
                ),
            },
            "legal_note": (
                "There is no Canadian law requiring 3× income. The 40% rule is the "
                "economist-backed standard. Agents enforcing 3× are applying extralegal discrimination."
            ),
        }

    def _savings_qualification(self, args: dict) -> dict:
        rent = float(args["monthly_rent"])
        savings = float(args["savings_cad"])
        six_months = round(rent * 6, 2)
        twelve_months = round(rent * 12, 2)
        qualifies_6 = savings >= six_months
        qualifies_12 = savings >= twelve_months
        return {
            "monthly_rent": rent,
            "savings_cad": savings,
            "six_months_threshold": six_months,
            "twelve_months_threshold": twelve_months,
            "qualifies_via_6_month_rule": qualifies_6,
            "qualifies_via_12_month_rule": qualifies_12,
            "shortfall_to_6_months": max(0, six_months - savings),
            "verdict": (
                "Qualifies via savings (6-month rule)." if qualifies_6
                else f"Does not meet 6-month savings threshold. Shortfall: ${max(0, six_months - savings):,.2f} CAD."
            ),
        }

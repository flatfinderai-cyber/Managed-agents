# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import os
from supabase import create_client

router = APIRouter()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)


class AgentReport(BaseModel):
    agent_id: Optional[str] = None
    agent_name_raw: Optional[str] = None
    agent_company_raw: Optional[str] = None
    user_id: Optional[str] = None
    violation_type: str
    severity: str = "medium"
    description: str
    financial_harm_cad: Optional[float] = None
    cities_affected: List[str] = []


@router.get("/search")
async def search_agents(
    name: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    blacklisted_only: bool = Query(False),
):
    """Search agents by name, city, or compliance status."""
    query = supabase.table("agents").select(
        "id, name, company, city, cities_active, compliance_score, "
        "status, is_blacklisted, blacklist_reason, human_rights_flags, "
        "income_requirement_multiplier, uses_illegal_screening, report_count"
    )

    if name:
        query = query.ilike("name", f"%{name}%")
    if city:
        query = query.contains("cities_active", [city])
    if status:
        query = query.eq("status", status)
    if blacklisted_only:
        query = query.eq("is_blacklisted", True)

    result = query.order("compliance_score", desc=False).limit(50).execute()
    return {"agents": result.data, "count": len(result.data)}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get full agent profile including violations."""
    agent = supabase.table("agents").select("*").eq("id", agent_id).single().execute()
    if not agent.data:
        raise HTTPException(status_code=404, detail="Agent not found")

    violations = supabase.table("agent_violations").select("*").eq(
        "agent_id", agent_id
    ).execute()

    return {
        "agent": agent.data,
        "violations": violations.data,
    }


@router.get("/{agent_id}/compliance")
async def get_agent_compliance(agent_id: str):
    """Returns compliance score and recommendation for an agent."""
    agent = supabase.table("agents").select(
        "compliance_score, status, is_blacklisted, blacklist_reason, "
        "human_rights_flags, income_requirement_multiplier, uses_illegal_screening"
    ).eq("id", agent_id).single().execute()

    if not agent.data:
        raise HTTPException(status_code=404, detail="Agent not found")

    a = agent.data
    if a["is_blacklisted"]:
        recommendation = "blacklisted"
    elif a["compliance_score"] < 50:
        recommendation = "avoid"
    elif a["compliance_score"] < 70:
        recommendation = "caution"
    else:
        recommendation = "safe"

    return {
        "compliance_score": a["compliance_score"],
        "status": a["status"],
        "is_blacklisted": a["is_blacklisted"],
        "blacklist_reason": a["blacklist_reason"],
        "recommendation": recommendation,
        "uses_illegal_screening": a["uses_illegal_screening"],
        "income_multiplier": a["income_requirement_multiplier"],
    }


@router.post("/report")
async def report_agent(report: AgentReport):
    """Submit a community report against an agent."""
    if not report.violation_type or not report.description:
        raise HTTPException(status_code=400, detail="violation_type and description are required")

    financial_cents = int(report.financial_harm_cad * 100) if report.financial_harm_cad else None

    result = supabase.table("agent_reports").insert({
        "agent_id": report.agent_id,
        "agent_name_raw": report.agent_name_raw,
        "agent_company_raw": report.agent_company_raw,
        "user_id": report.user_id,
        "violation_type": report.violation_type,
        "severity": report.severity,
        "description": report.description,
        "financial_harm": financial_cents,
        "cities_affected": report.cities_affected,
    }).execute()

    return {
        "success": True,
        "message": "Report received. Every report helps protect the next renter. Thank you.",
        "report_id": result.data[0]["id"] if result.data else None,
    }


@router.get("/blacklist/all")
async def get_full_blacklist(city: Optional[str] = Query(None)):
    """Returns all blacklisted agents, optionally filtered by city."""
    query = supabase.table("agents").select(
        "id, name, company, city, cities_active, blacklist_reason, blacklist_date, "
        "compliance_score, human_rights_flags, un_violation_count"
    ).eq("is_blacklisted", True)

    if city:
        query = query.contains("cities_active", [city])

    result = query.order("compliance_score").execute()
    return {"blacklisted_agents": result.data, "count": len(result.data)}

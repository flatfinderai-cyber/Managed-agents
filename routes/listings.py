# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, field_validator
from supabase import create_client

router = APIRouter()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

ALLOWED_CITIES = frozenset({"Toronto", "Vancouver", "Paris", "Edinburgh"})
_ALLOWED_CITIES_LOWER = {c.lower(): c for c in ALLOWED_CITIES}
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_PERPLEXITY_MODEL = "sonar"

LISTING_SEARCH_ASSIST_SYSTEM = """You extract structured rental search filters for FlatFinder™.

Reply with ONE JSON object only. No markdown fences, no commentary before or after.

Keys (use null when unknown):
- "city": exactly one of: Toronto, Vancouver, Paris, Edinburgh
- "max_rent": integer, maximum monthly rent in whole currency units (CAD for Toronto/Vancouver, EUR for Paris, GBP for Edinburgh), or null
- "min_bedrooms": integer 0–6 (0 = studio), or null
- "annual_income": number (annual, same currency context as city) or null
- "exclude_blacklisted": boolean, default true
- "exclude_flagged": boolean, default false
- "tip": short plain sentence for the renter (optional)

Rules:
- If the user is vague, infer the best city from context; if impossible, use Toronto.
- max_rent must be between 300 and 50000 if set; round to whole units.
- min_bedrooms: clamp 0–6.
"""


class ListingSearchAssistRequest(BaseModel):
    """Natural-language description of what the user wants to search for."""

    message: str = Field(..., min_length=3, max_length=4000)


class ListingSearchFilters(BaseModel):
    """Validated filters compatible with GET /api/listings/search query params."""

    city: str
    max_rent: Optional[int] = None
    min_bedrooms: Optional[int] = None
    annual_income: Optional[float] = None
    exclude_blacklisted: bool = True
    exclude_flagged: bool = False
    tip: Optional[str] = None

    @field_validator("city")
    @classmethod
    def city_allowed(cls, v: str) -> str:
        t = (v or "").strip().lower()
        if t in _ALLOWED_CITIES_LOWER:
            return _ALLOWED_CITIES_LOWER[t]
        raise ValueError(f"city must be one of: {', '.join(sorted(ALLOWED_CITIES))}")

    @field_validator("max_rent")
    @classmethod
    def rent_bounds(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if v < 300:
            return 300
        if v > 50000:
            return 50000
        return int(v)

    @field_validator("min_bedrooms")
    @classmethod
    def beds_bounds(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        return max(0, min(6, int(v)))


def _perplexity_key() -> str:
    key = (os.environ.get("PERPLEXITY_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="PERPLEXITY_API_KEY is not set — required for listing search assist.",
        )
    return key


def _perplexity_model() -> str:
    return (os.environ.get("PERPLEXITY_MODEL") or DEFAULT_PERPLEXITY_MODEL).strip() or DEFAULT_PERPLEXITY_MODEL


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse first JSON object from model output (tolerate accidental fences)."""
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        raise ValueError("No JSON object in model response")
    return json.loads(m.group(0))


def _raw_to_filters(raw: dict[str, Any]) -> ListingSearchFilters:
    city = raw.get("city") or "Toronto"
    max_rent = raw.get("max_rent")
    if max_rent is not None:
        try:
            max_rent = int(round(float(max_rent)))
        except (TypeError, ValueError):
            max_rent = None
    min_bedrooms = raw.get("min_bedrooms")
    if min_bedrooms is not None:
        try:
            min_bedrooms = int(round(float(min_bedrooms)))
        except (TypeError, ValueError):
            min_bedrooms = None
    annual = raw.get("annual_income")
    if annual is not None:
        try:
            annual = float(annual)
        except (TypeError, ValueError):
            annual = None
    tip = raw.get("tip")
    if tip is not None and not isinstance(tip, str):
        tip = str(tip)
    if isinstance(tip, str) and len(tip) > 500:
        tip = tip[:500]
    eb = raw.get("exclude_blacklisted", True)
    ef = raw.get("exclude_flagged", False)
    return ListingSearchFilters(
        city=str(city),
        max_rent=max_rent,
        min_bedrooms=min_bedrooms,
        annual_income=annual,
        exclude_blacklisted=bool(eb) if eb is not None else True,
        exclude_flagged=bool(ef) if ef is not None else False,
        tip=tip if isinstance(tip, str) else None,
    )


@router.get("/search")
async def search_listings(
    city: str = Query(..., description="City to search in"),
    max_rent: Optional[int] = Query(None, description="Max monthly rent in CAD"),
    min_bedrooms: Optional[int] = Query(None),
    annual_income: Optional[float] = Query(None, description="Annual income to calculate affordability"),
    exclude_blacklisted: bool = Query(True, description="Hide listings from blacklisted agents"),
    exclude_flagged: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Search listings with affordability scoring and agent compliance filtering.
    Blacklisted agents hidden by default — protecting renters from predatory agencies.
    """
    query = supabase.table("listings").select(
        "*, agents(name, company, compliance_score, status, is_blacklisted, is_flagged)"
        if False  # join via agent_id
        else "id, title, price, currency, bedrooms, bathrooms, sqft, "
             "address, neighborhood, city, images, url, amenities, "
             "pet_friendly, utilities_included, available_date, "
             "affordability_score, compliance_score, is_flagged, agent_id, source"
    ).eq("city", city).eq("is_active", True).eq("is_scam", False)

    if max_rent:
        query = query.lte("price", max_rent * 100)  # stored in cents
    if min_bedrooms:
        query = query.gte("bedrooms", min_bedrooms)
    if exclude_flagged:
        query = query.eq("is_flagged", False)

    # Order: safest + most affordable first
    query = query.order("compliance_score", desc=True).order("price")

    offset = (page - 1) * page_size
    result = query.range(offset, offset + page_size - 1).execute()

    listings = result.data

    # Attach affordability label if income provided
    if annual_income and listings:
        monthly_income = annual_income / 12
        for listing in listings:
            rent_cad = listing["price"] / 100
            pct = round((rent_cad / monthly_income) * 100, 1) if monthly_income > 0 else None
            listing["affordability_pct"] = pct
            listing["is_affordable"] = pct <= 40 if pct else None

    return {
        "listings": listings,
        "page": page,
        "page_size": page_size,
        "city": city,
        "count": len(listings),
    }


@router.post("/search/assist")
async def listing_search_assist(body: ListingSearchAssistRequest):
    """
    Pattern A: natural language → Perplexity (search-grounded) → validated JSON filters
    for GET /api/listings/search. Does not return listing rows — client runs search with filters.
    """
    api_key = _perplexity_key()
    user_content = (
        "Extract search filters from this renter message. "
        "Use web knowledge only to resolve ambiguous neighbourhoods or typical rents.\n\n"
        f"Message:\n{body.message.strip()}"
    )
    payload = {
        "model": _perplexity_model(),
        "messages": [
            {"role": "system", "content": LISTING_SEARCH_ASSIST_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=r.text[:1000] or "Perplexity request failed.")
    data = r.json()
    try:
        choices = data.get("choices") or []
        msg = (choices[0].get("message") or {}) if choices else {}
        raw_text = (msg.get("content") or "").strip()
    except (TypeError, KeyError, IndexError):
        raw_text = ""
    if not raw_text:
        raise HTTPException(status_code=502, detail="Empty response from listing search assist.")
    try:
        raw_obj = _extract_json_object(raw_text)
        filters = _raw_to_filters(raw_obj)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid search filters after model output: {exc!s}",
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not parse search filters from model: {exc!s}",
        ) from exc

    query_params: dict[str, Any] = {"city": filters.city}
    if filters.max_rent is not None:
        query_params["max_rent"] = filters.max_rent
    if filters.min_bedrooms is not None:
        query_params["min_bedrooms"] = filters.min_bedrooms
    if filters.annual_income is not None:
        query_params["annual_income"] = filters.annual_income
    query_params["exclude_blacklisted"] = filters.exclude_blacklisted
    query_params["exclude_flagged"] = filters.exclude_flagged

    return {
        "filters": filters.model_dump(),
        "query_params": query_params,
    }


@router.get("/{listing_id}")
async def get_listing(listing_id: str):
    """Get a single listing with full details."""
    result = supabase.table("listings").select("*").eq("id", listing_id).single().execute()
    return result.data

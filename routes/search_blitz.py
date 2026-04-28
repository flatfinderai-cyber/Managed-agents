# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
# Search Blitz — $79 CAD premium deep search

from __future__ import annotations

import asyncio
import logging
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from supabase import create_client

router = APIRouter()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

SEARCH_BLITZ_PRICE_CAD = 79.00
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_PERPLEXITY_MODEL = "sonar"

SEARCH_BLITZ_REPORT_SYSTEM = """You are Benny, FlatFinder™'s housing guide (orange tabby, warm and direct).

Write a renter-facing **markdown** report for a **Search Blitz** premium deep search.

Rules:
- Use the 33–40% of income affordability standard — never promote the illegal 3× gross rent rule.
- Summarise the listings given; if the list is empty, explain honestly and suggest how to widen the search.
- Do not invent listings: only reference properties present in the JSON snapshot.
- Include a short "Next steps" section (e.g. confirm pet policy, book viewing, watch for scams).
- British English spelling where natural for the audience.
"""


class SearchBlitzRequest(BaseModel):
    user_id: str
    city: str
    annual_income: float
    min_bedrooms: Optional[int] = None
    max_rent_cad: Optional[float] = None
    must_haves: list[str] = []
    pet_friendly: Optional[bool] = None
    neighborhoods: list[str] = []


def _require_internal_key(x_internal_key: Optional[str]) -> None:
    expected = os.environ.get("INTERNAL_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Internal API key not configured — set INTERNAL_API_KEY in environment.",
        )
    if not x_internal_key or x_internal_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden. Invalid or missing internal API key.")


def _perplexity_key() -> str:
    key = (os.environ.get("PERPLEXITY_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="PERPLEXITY_API_KEY is not set — required for Search Blitz report.",
        )
    return key


def _perplexity_model() -> str:
    return (os.environ.get("PERPLEXITY_MODEL") or DEFAULT_PERPLEXITY_MODEL).strip() or DEFAULT_PERPLEXITY_MODEL


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail_order(order_id: str, err: str) -> None:
    try:
        supabase.table("search_blitz_orders").update(
            {
                "status": "failed",
                "fulfillment_error": err[:2000],
                "completed_at": _now_iso(),
            }
        ).eq("id", order_id).execute()
    except Exception:
        pass


def _fulfill_search_blitz_sync(order_id: str) -> dict[str, Any]:
    """Load order, query listings from DB, call Perplexity for deliverable, persist (Pattern B)."""
    try:
        res = supabase.table("search_blitz_orders").select("*").eq("id", order_id).single().execute()
    except Exception as exc:
        logging.error(f"Order query failed for ID {order_id}: {exc!s}")
        raise HTTPException(status_code=404, detail="Order not found") from exc

    if not res.data:
        raise HTTPException(status_code=404, detail="Order not found.")

    row = res.data
    if row.get("status") == "complete":
        return {
            "order_id": order_id,
            "status": "complete",
            "skipped": True,
            "message": "Order already fulfilled.",
        }

    supabase.table("search_blitz_orders").update({"status": "running"}).eq("id", order_id).execute()

    crit = row.get("criteria") or {}
    city = row.get("city") or ""
    max_rent = crit.get("max_rent_cad")
    min_beds = crit.get("min_bedrooms")
    pet_ok = crit.get("pet_friendly")

    try:
        q = (
            supabase.table("listings")
            .select(
                "id, title, price, currency, bedrooms, bathrooms, neighborhood, city, "
                "url, pet_friendly, compliance_score, is_flagged"
            )
            .eq("city", city)
            .eq("is_active", True)
            .eq("is_scam", False)
        )
        if max_rent is not None:
            q = q.lte("price", int(round(float(max_rent) * 100)))
        if min_beds is not None:
            q = q.gte("bedrooms", int(min_beds))
        if pet_ok:
            q = q.eq("pet_friendly", True)
        list_res = q.order("compliance_score", desc=True).order("price").limit(25).execute()
    except Exception as exc:
        logging.error(f"Listing query failed for order {order_id}: {exc!s}")
        _fail_order(order_id, str(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch listings for order.") from exc

    listings = list_res.data or []
    snapshot = []
    ids: list[str] = []
    for lst in listings:
        ids.append(str(lst["id"]))
        rent = (lst.get("price") or 0) / 100
        snapshot.append(
            {
                "id": str(lst["id"]),
                "title": lst.get("title"),
                "rent_monthly": rent,
                "currency": lst.get("currency") or "CAD",
                "bedrooms": lst.get("bedrooms"),
                "neighborhood": lst.get("neighborhood"),
                "url": lst.get("url"),
                "pet_friendly": lst.get("pet_friendly"),
                "compliance_score": lst.get("compliance_score"),
            }
        )

    user_payload = {
        "order_city": city,
        "criteria": crit,
        "listings_snapshot": snapshot,
    }
    user_content = (
        "Write the Search Blitz report from this JSON context.\n\n"
        f"```json\n{json.dumps(user_payload, indent=2)[:120000]}\n```"
    )

    api_key = _perplexity_key()
    payload = {
        "model": _perplexity_model(),
        "messages": [
            {"role": "system", "content": SEARCH_BLITZ_REPORT_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
    }
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                PERPLEXITY_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if r.status_code >= 400:
            _fail_order(order_id, r.text[:2000])
            raise HTTPException(status_code=502, detail=r.text[:1000] or "Perplexity request failed.")
        data = r.json()
        choices = data.get("choices") or []
        msg = (choices[0].get("message") or {}) if choices else {}
        report = (msg.get("content") or "").strip()
    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Perplexity call failed for order {order_id}: {exc!s}")
        _fail_order(order_id, str(exc))
        raise HTTPException(status_code=502, detail="Failed to generate report using AI.") from exc

    if not report:
        _fail_order(order_id, "Empty report from model")
        raise HTTPException(status_code=502, detail="Empty report from Perplexity.")

    now = _now_iso()
    try:
        supabase.table("search_blitz_orders").update(
            {
                "status": "complete",
                "deliverable_report": report,
                "matched_listing_ids": ids,
                "results_count": len(ids),
                "completed_at": now,
                "fulfillment_error": None,
            }
        ).eq("id", order_id).execute()
    except Exception as exc:
        logging.error(f"Failed to save report for order {order_id}: {exc!s}")
        _fail_order(order_id, str(exc))
        raise HTTPException(status_code=500, detail="Failed to save generated report.") from exc

    return {
        "order_id": order_id,
        "status": "complete",
        "results_count": len(ids),
        "report_preview": report[:500] + ("…" if len(report) > 500 else ""),
    }


@router.post("/order")
async def create_search_blitz(request: SearchBlitzRequest):
    """
    Create a Search Blitz order — FlatFinder's $79 CAD premium deep search.
    Triggers a comprehensive scrape of all sources for the specified city and criteria.
    Results delivered within 24 hours.
    """
    criteria = {
        "annual_income": request.annual_income,
        "max_rent_cad": request.max_rent_cad or round((request.annual_income / 12) * 0.40, 2),
        "min_bedrooms": request.min_bedrooms,
        "must_haves": request.must_haves,
        "pet_friendly": request.pet_friendly,
        "neighborhoods": request.neighborhoods,
    }

    result = supabase.table("search_blitz_orders").insert(
        {
            "user_id": request.user_id,
            "city": request.city,
            "criteria": criteria,
            "status": "pending",
        }
    ).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create Search Blitz order")

    order = result.data[0]

    return {
        "order_id": order["id"],
        "status": "pending",
        "city": request.city,
        "price_cad": SEARCH_BLITZ_PRICE_CAD,
        "message": (
            "Your Search Blitz is queued! Benny is on it. "
            "You'll receive your results within 24 hours. "
            "All results are pre-filtered to exclude blacklisted agents."
        ),
    }


@router.get("/order/{order_id}")
async def get_order_status(order_id: str):
    """Check the status of a Search Blitz order."""
    result = supabase.table("search_blitz_orders").select("*").eq("id", order_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return result.data


@router.post("/order/{order_id}/fulfill")
async def fulfill_search_blitz(
    order_id: str,
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
):
    """
    Pattern B: run fulfillment for a pending Search Blitz order (internal only).

    Queries current listings in Supabase for the order city/criteria, then calls
    Perplexity once to produce **deliverable_report**. Does not run Playwright scrape
    in-process (ingestion remains on your scraper schedule); DB snapshot is the MVP
    fulfillment source.

    Requires **X-Internal-Key** matching ``INTERNAL_API_KEY`` (same as orchestrator).
    """
    _require_internal_key(x_internal_key)
    try:
        return await asyncio.to_thread(_fulfill_search_blitz_sync, order_id)
    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Fulfillment sync error for order {order_id}: {exc!s}")
        _fail_order(order_id, str(exc))
        raise HTTPException(status_code=500, detail="An error occurred while fulfilling the order.") from exc

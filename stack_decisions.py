# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™

import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from supabase import create_client

router = APIRouter()

_sb = create_client(
    os.environ.get("SUPABASE_URL", ""),
    os.environ.get("SUPABASE_SERVICE_KEY", ""),
)


def _require_internal_key(x_internal_key: Optional[str]) -> None:
    expected = os.environ.get("INTERNAL_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Internal API key not configured — set INTERNAL_API_KEY in environment.",
        )
    if not x_internal_key or x_internal_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden. Invalid or missing internal API key.")


@router.get("/queue")
async def get_stack_decision_queue(
    decision: Optional[str] = Query(None, pattern="^(pass|quarantine|block)$"),
    limit: int = Query(100, ge=1, le=500),
    x_internal_key: Optional[str] = Header(None),
):
    """
    Internal moderation view of latest listing stack decisions.
    """
    _require_internal_key(x_internal_key)

    try:
        query = (
            _sb.table("listing_stack_decisions")
            .select("*, listings(id, source, city, title, url, is_active, is_flagged, is_scam)")
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if decision:
            query = query.eq("decision", decision)

        result = query.execute()
    except Exception as exc:
        logging.error(f"Database error: {str(exc)}")
        raise HTTPException(status_code=503, detail="A database error occurred. Please try again later.")

    rows = result.data or []
    return {"count": len(rows), "items": rows}


@router.get("/{listing_id}")
async def get_listing_stack_decision(
    listing_id: str,
    x_internal_key: Optional[str] = Header(None),
):
    """Return current stack decision plus latest historical events for a listing."""
    _require_internal_key(x_internal_key)

    try:
        latest = (
            _sb.table("listing_stack_decisions")
            .select("*")
            .eq("listing_id", listing_id)
            .single()
            .execute()
        )

        events = (
            _sb.table("listing_stack_decision_events")
            .select("*")
            .eq("listing_id", listing_id)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
    except Exception as exc:
        logging.error(f"Database error: {str(exc)}")
        raise HTTPException(status_code=503, detail="A database error occurred. Please try again later.")

    if not latest.data:
        raise HTTPException(status_code=404, detail="No stack decision found for listing.")

    return {
        "current": latest.data,
        "events": events.data or [],
    }

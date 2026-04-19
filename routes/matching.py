# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — matching.py
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.
#
# FF-CORE-011: 6-Filter Matching Engine
# Anti-Gatekeeping Affordability Algorithm™ (Proprietary)
#
# CRITICAL RULES:
#   - The landlord NEVER sees: tenant rank, tenant documentation tier, tenant affordability score.
#   - The landlord only sees: "A verified tenant has been matched to your listing."
#   - Affordability uses 40% of NET income. NEVER 3× gross rent.
#   - Credit score is never a filter gate.
#   - Filters are applied in order 1–6. A listing fails at the first failing filter.

import os
import uuid
from datetime import datetime, date, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

from deps.supabase_auth import CurrentUserId, assert_same_user

router = APIRouter(tags=["Matching Engine"])

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

_sb = create_client(
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""),
    os.environ.get("SUPABASE_SERVICE_KEY", ""),
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _db_error(exc: Exception) -> HTTPException:
    if not os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"):
        return HTTPException(
            status_code=503,
            detail="Database not configured — add credentials to .env.local",
        )
    return HTTPException(status_code=503, detail=f"Database error: {str(exc)}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _months_between(d1: date, d2: date) -> float:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def _match_tenant_id(m: dict) -> Optional[str]:
    return m.get("tenant_user_id") or m.get("tenant_id")


def _match_landlord_id(m: dict) -> Optional[str]:
    return m.get("landlord_user_id") or m.get("landlord_id")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RunMatchRequest(BaseModel):
    tenant_user_id: str
    listing_ids: Optional[List[str]] = None     # Empty = all active listings


class ConfirmMatchRequest(BaseModel):
    match_id: str
    user_id: str
    role: str                                   # "tenant" | "landlord"


# ---------------------------------------------------------------------------
# Filter engine
# ---------------------------------------------------------------------------


def _apply_filters(tenant: dict, listing: dict, landlord: dict) -> dict:
    """
    Apply all 6 filters in order. Return a result dict with pass/fail per filter.
    Stops evaluation at the first failing filter for this listing.
    No scores or algorithm weights are included in the output.
    Credit score is never referenced.
    """
    today = date.today()
    results = {}

    # ------------------------------------------------------------------
    # Filter 1: Listing quality gates
    #   - Landlord must be verified
    #   - Listing must have a floor plan
    #   - Last inspection must be within 24 months
    # ------------------------------------------------------------------
    f1_landlord_verified = landlord.get("verification_status") == "verified"
    listing_details = listing.get("listing_details") or {}
    f1_has_floor_plan = bool(listing_details.get("floor_plan_storage_path"))
    last_inspection_str = listing_details.get("last_inspection_date") or listing.get("last_inspection_date")
    last_inspection = _parse_date(last_inspection_str)
    if last_inspection:
        months_since = _months_between(last_inspection, today)
        f1_inspection_current = months_since <= 24
    else:
        f1_inspection_current = False

    f1_pass = f1_landlord_verified and f1_has_floor_plan and f1_inspection_current
    results["filter_1_listing_quality"] = {
        "pass": f1_pass,
        "landlord_verified": f1_landlord_verified,
        "floor_plan_present": f1_has_floor_plan,
        "inspection_within_24_months": f1_inspection_current,
    }
    if not f1_pass:
        return results

    # ------------------------------------------------------------------
    # Filter 2: Tenant verification
    # ------------------------------------------------------------------
    f2_pass = tenant.get("verification_status") == "verified"
    results["filter_2_tenant_verified"] = {"pass": f2_pass}
    if not f2_pass:
        return results

    # ------------------------------------------------------------------
    # Filter 3: Geographic and property type match
    # ------------------------------------------------------------------
    desired_cities = tenant.get("desired_cities") or []
    desired_types = tenant.get("desired_property_types") or []
    listing_city = (listing.get("city") or "").strip().lower()
    listing_type = (listing.get("property_type") or "").strip().lower()

    city_match = any(c.strip().lower() == listing_city for c in desired_cities) if desired_cities else True
    type_match = any(t.strip().lower() == listing_type for t in desired_types) if desired_types else True

    f3_pass = city_match and type_match
    results["filter_3_location_and_type"] = {
        "pass": f3_pass,
        "city_match": city_match,
        "property_type_match": type_match,
    }
    if not f3_pass:
        return results

    # ------------------------------------------------------------------
    # Filter 4: Availability window
    # ------------------------------------------------------------------
    available_date = _parse_date(listing.get("available_date"))
    move_in_from = _parse_date(tenant.get("desired_move_in_from"))
    move_in_to = _parse_date(tenant.get("desired_move_in_to"))

    if available_date and move_in_from and move_in_to:
        f4_pass = move_in_from <= available_date <= move_in_to
    elif available_date and move_in_from:
        f4_pass = available_date >= move_in_from
    elif available_date and move_in_to:
        f4_pass = available_date <= move_in_to
    else:
        f4_pass = True  # No window specified — not a disqualifier

    results["filter_4_availability"] = {
        "pass": f4_pass,
        "listing_available_date": listing.get("available_date"),
        "tenant_window_from": tenant.get("desired_move_in_from"),
        "tenant_window_to": tenant.get("desired_move_in_to"),
    }
    if not f4_pass:
        return results

    # ------------------------------------------------------------------
    # Filter 5: Non-negotiables
    # ------------------------------------------------------------------
    non_negotiables = tenant.get("non_negotiables") or {}
    f5_failures = []

    for requirement, required_value in non_negotiables.items():
        listing_value = listing_details.get(requirement) if listing_details else listing.get(requirement)
        if listing_value is None:
            listing_value = listing.get(requirement)
        if required_value is True and not listing_value:
            f5_failures.append(requirement)
        elif required_value is False and listing_value:
            f5_failures.append(requirement)
        elif isinstance(required_value, str) and isinstance(listing_value, str):
            if required_value.lower() != listing_value.lower():
                f5_failures.append(requirement)

    f5_pass = len(f5_failures) == 0
    results["filter_5_non_negotiables"] = {
        "pass": f5_pass,
        "unmet_requirements": f5_failures if not f5_pass else [],
    }
    if not f5_pass:
        return results

    # ------------------------------------------------------------------
    # Filter 6: No active discrimination or predatory flags
    # ------------------------------------------------------------------
    listing_id = listing.get("id")
    landlord_user_id = landlord.get("user_id")

    try:
        flag_result = (
            _sb.table("discrimination_flags")
            .select("id")
            .or_(f"listing_id.eq.{listing_id},subject_id.eq.{landlord_user_id}")
            .eq("active", True)
            .limit(1)
            .execute()
        )
        f6_pass = len(flag_result.data or []) == 0
    except Exception:
        # If flags cannot be checked, err on the side of caution
        f6_pass = False

    results["filter_6_no_active_flags"] = {"pass": f6_pass}
    if not f6_pass:
        return results

    return results


def _all_passed(filter_results: dict) -> bool:
    return all(v.get("pass", False) for v in filter_results.values())


def _calculate_affordability(tenant: dict, listing: dict) -> Optional[float]:
    """
    Return rent as a percentage of net monthly income.
    Uses 40% of NET income. Never 3× gross rent. Credit score never referenced.
    Returns None if income data is unavailable.
    """
    rent_cents = listing.get("price") or listing.get("rent_cents")
    if not rent_cents:
        return None

    # Net monthly income sourced from tenant profile (stored from tier-2 verification)
    net_monthly_income_cents = tenant.get("net_monthly_income_cents")
    if not net_monthly_income_cents or net_monthly_income_cents <= 0:
        return None

    return round((rent_cents / net_monthly_income_cents) * 100, 2)


def _compliance_score(landlord: dict) -> float:
    """Return landlord compliance score for ranking. Defaults to 0.0 if not present."""
    return float(landlord.get("compliance_score") or 0.0)


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------


@router.post("/run")
async def run_matching(body: RunMatchRequest, current: CurrentUserId):
    """
    Run the 6-filter matching engine for a tenant.
    Anti-Gatekeeping Affordability Algorithm™ applied after all filters.

    Ranking order (proprietary — weights not exposed):
        1. affordability_pct ASC (lower is better)
        2. compliance_score DESC (higher is better)
        3. available_date ASC (sooner is better)

    The landlord view is intentionally omitted from this response.
    No ranks, no tiers, no scores are surfaced to any landlord.
    """
    assert_same_user(body.tenant_user_id, current)
    tenant_user_id = body.tenant_user_id

    # Fetch tenant profile
    try:
        tenant_result = (
            _sb.table("tenant_profiles")
            .select("*")
            .eq("user_id", tenant_user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not tenant_result.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")

    tenant = tenant_result.data

    # Fetch listings
    try:
        listing_query = (
            _sb.table("listings")
            .select("*")
            .eq("is_active", True)
        )
        if body.listing_ids:
            listing_query = listing_query.in_("id", body.listing_ids)

        listing_result = listing_query.execute()
    except Exception as exc:
        raise _db_error(exc)

    listings = listing_result.data or []

    if not listings:
        return {"tenant_user_id": tenant_user_id, "matches": [], "total_evaluated": 0}

    # Gather all unique landlord profile user_ids
    landlord_user_ids = list({lst.get("landlord_user_id") for lst in listings if lst.get("landlord_user_id")})

    try:
        landlord_result = (
            _sb.table("landlord_profiles")
            .select("*")
            .in_("user_id", landlord_user_ids)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    landlord_map = {lp["user_id"]: lp for lp in (landlord_result.data or [])}

    # Run filters and collect passing matches
    passed_matches = []

    for listing in listings:
        landlord_user_id = listing.get("landlord_user_id")
        landlord = landlord_map.get(landlord_user_id, {})

        filter_results = _apply_filters(tenant, listing, landlord)
        passed = _all_passed(filter_results)

        if passed:
            affordability_pct = _calculate_affordability(tenant, listing)
            is_affordable = (affordability_pct <= 40.0) if affordability_pct is not None else None
            available_date = listing.get("available_date") or "9999-12-31"

            passed_matches.append({
                "listing_id": listing["id"],
                "landlord_user_id": landlord_user_id,
                "affordability_pct": affordability_pct,
                "is_affordable": is_affordable,
                "compliance_score": _compliance_score(landlord),
                "available_date": available_date,
                "filter_results": filter_results,
                "listing_snapshot": {
                    "city": listing.get("city"),
                    "property_type": listing.get("property_type"),
                    "rent_cents": listing.get("price") or listing.get("rent_cents"),
                    "available_date": listing.get("available_date"),
                    "bedrooms": listing.get("bedrooms"),
                },
            })

    # Anti-Gatekeeping Affordability Algorithm™
    # Rank: affordability_pct ASC, compliance_score DESC, available_date ASC
    def _sort_key(m: dict):
        aff = m["affordability_pct"] if m["affordability_pct"] is not None else 999.0
        comp = -m["compliance_score"]          # negate for DESC
        avail = m["available_date"] or "9999-12-31"
        return (aff, comp, avail)

    passed_matches.sort(key=_sort_key)

    # Upsert match records
    now = _now()
    upserted_matches = []

    for rank_index, match in enumerate(passed_matches):
        listing_id = match["listing_id"]

        try:
            existing = (
                _sb.table("matches")
                .select("id, status")
                .eq("tenant_user_id", tenant_user_id)
                .eq("listing_id", listing_id)
                .execute()
            )
        except Exception as exc:
            raise _db_error(exc)

        match_record = {
            "tenant_user_id": tenant_user_id,
            "listing_id": listing_id,
            "filter_results": match["filter_results"],
            "affordability_pct": match["affordability_pct"],
            "is_affordable": match["is_affordable"],
            # rank is internal only — never exposed to landlord
            "internal_rank": rank_index + 1,
            "updated_at": now,
        }

        try:
            if existing.data:
                record_id = existing.data[0]["id"]
                # Do not overwrite a confirmed match status
                if existing.data[0].get("status") not in ("confirmed_both",):
                    match_record["status"] = "matched"
                result = (
                    _sb.table("matches")
                    .update(match_record)
                    .eq("id", record_id)
                    .execute()
                )
                saved = result.data[0] if result.data else {**match_record, "id": record_id}
            else:
                match_record["id"] = str(uuid.uuid4())
                match_record["status"] = "matched"
                match_record["created_at"] = now
                result = _sb.table("matches").insert(match_record).execute()
                saved = result.data[0] if result.data else match_record
        except Exception as exc:
            raise _db_error(exc)

        upserted_matches.append({
            "match_id": saved.get("id", match_record.get("id")),
            "listing_id": listing_id,
            "filter_results": match["filter_results"],
            "affordability_pass": match["is_affordable"],
            "listing_snapshot": match["listing_snapshot"],
            # No rank, no tier, no score surfaced
        })

    return {
        "tenant_user_id": tenant_user_id,
        "total_evaluated": len(listings),
        "total_matched": len(upserted_matches),
        "matches": upserted_matches,
    }


# ---------------------------------------------------------------------------
# GET /tenant/{tenant_user_id}
# ---------------------------------------------------------------------------


@router.get("/tenant/{tenant_user_id}")
async def get_matches_for_tenant(tenant_user_id: str, current: CurrentUserId):
    """
    Return all matches for a tenant, in ranked order.
    Tenant-facing only — affordability and filter results are included.
    """
    assert_same_user(tenant_user_id, current)
    try:
        result = (
            _sb.table("matches")
            .select("*")
            .eq("tenant_id", tenant_user_id)
            .order("rank_position")
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    matches = result.data or []

    # Do not expose rank as a labelled position to clients
    for m in matches:
        m.pop("rank_position", None)

    return {"tenant_user_id": tenant_user_id, "total": len(matches), "matches": matches}


# ---------------------------------------------------------------------------
# GET /listing/{listing_id}
# ---------------------------------------------------------------------------


@router.get("/listing/{listing_id}")
async def get_matches_for_listing(listing_id: str, current: CurrentUserId):
    """
    Return all matches for a listing (landlord view).
    CRITICAL: No rank, no score, no tier is surfaced.
    The landlord only sees that a verified tenant has been matched.
    """
    try:
        owner = (
            _sb.table("listings")
            .select("landlord_user_id")
            .eq("id", listing_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not owner.data or not owner.data.get("landlord_user_id"):
        raise HTTPException(status_code=404, detail="Listing not found.")
    assert_same_user(owner.data["landlord_user_id"], current)

    try:
        result = (
            _sb.table("matches")
            .select("id, status, created_at, updated_at, confirmed_tenant_at, confirmed_landlord_at, listing_id")
            .eq("listing_id", listing_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    matches = result.data or []

    # Sanitise — strip any accidentally stored internal fields
    landlord_safe = [
        {
            "match_id": m.get("id"),
            "listing_id": m.get("listing_id"),
            "status": m.get("status"),
            "confirmed_tenant_at": m.get("confirmed_tenant_at"),
            "confirmed_landlord_at": m.get("confirmed_landlord_at"),
            "created_at": m.get("created_at"),
            # All that the landlord sees:
            "message": "A verified tenant has been matched to your listing.",
        }
        for m in matches
    ]

    return {"listing_id": listing_id, "total": len(landlord_safe), "matches": landlord_safe}


# ---------------------------------------------------------------------------
# POST /confirm
# ---------------------------------------------------------------------------


@router.post("/confirm")
async def confirm_match(body: ConfirmMatchRequest, current: CurrentUserId):
    """
    Confirm a match as tenant or landlord.
    When both parties confirm, status is set to 'confirmed_both' and a
    VMC (Verified Match Confirmation) thread is created.
    """
    if body.role not in ("tenant", "landlord"):
        raise HTTPException(status_code=422, detail="role must be 'tenant' or 'landlord'.")

    assert_same_user(body.user_id, current)

    # Fetch match
    try:
        match_result = (
            _sb.table("matches")
            .select("*")
            .eq("id", body.match_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not match_result.data:
        raise HTTPException(status_code=404, detail="Match not found.")

    match = match_result.data
    tid = _match_tenant_id(match)
    lid = _match_landlord_id(match)
    if body.role == "tenant":
        if not tid or tid != body.user_id:
            raise HTTPException(status_code=403, detail="Cannot confirm as tenant for this match.")
    else:
        if not lid or lid != body.user_id:
            raise HTTPException(status_code=403, detail="Cannot confirm as landlord for this match.")
    now = _now()

    update_payload: dict = {"updated_at": now}

    if body.role == "tenant":
        update_payload["confirmed_tenant_at"] = now
    else:
        update_payload["confirmed_landlord_at"] = now

    # Determine whether both parties have now confirmed
    tenant_confirmed = match.get("confirmed_tenant_at") or (body.role == "tenant")
    landlord_confirmed = match.get("confirmed_landlord_at") or (body.role == "landlord")

    both_confirmed = bool(tenant_confirmed and landlord_confirmed)
    if both_confirmed:
        update_payload["status"] = "confirmed_both"
        update_payload["confirmed_both_at"] = now

    try:
        result = (
            _sb.table("matches")
            .update(update_payload)
            .eq("id", body.match_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    # When both confirm, create a VMC thread
    vmc_thread_id = None
    if both_confirmed:
        vmc_thread_id = str(uuid.uuid4())
        tid = _match_tenant_id(match)
        lid = _match_landlord_id(match)
        vmc_record = {
            "id": vmc_thread_id,
            "match_id": body.match_id,
            "listing_id": match.get("listing_id"),
            "tenant_id": tid,
            "landlord_id": lid,
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        try:
            _sb.table("vmc_threads").insert(vmc_record).execute()
        except Exception:
            # VMC thread creation failure is non-fatal for the confirmation flow
            pass

    return {
        "match_id": body.match_id,
        "role_confirmed": body.role,
        "status": update_payload.get("status", match.get("status")),
        "both_confirmed": both_confirmed,
        "vmc_thread_id": vmc_thread_id,
        "profile": result.data[0] if result.data else {},
    }

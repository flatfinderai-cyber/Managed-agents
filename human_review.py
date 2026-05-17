# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — human_review.py
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.
#
# FF-CORE-008: Human Review Framework
#
# SLA TIERS:
#   tier1 = 48 hours
#   tier2 = 5 business days
#   tier3 = 10 business days
#
# FLAG RULES:
#   confidence_score >= 0.85  → auto-ban: account_banned, do_not_fly_list, listing inactive
#   confidence_score >= 0.60  → suspend listing + queue human_review tier=1 within 24h
#   flag_type = 'predatory'   → mandatory law_enforcement referral regardless of confidence score
#
# Admin routes require x-internal-key header matching INTERNAL_API_KEY env var.

import secrets
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

router = APIRouter(tags=["Human Review"])

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

_sb = create_client(
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""),
    os.environ.get("SUPABASE_SERVICE_KEY", ""),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUSINESS_HOURS_PER_DAY = 8
# SLA in hours per tier
TIER_SLA_HOURS = {
    1: 48,
    2: 5 * BUSINESS_HOURS_PER_DAY,  # 5 business days = 40h
    3: 10 * BUSINESS_HOURS_PER_DAY,  # 10 business days = 80h
}

VALID_OUTCOMES = {"cleared", "found_against", "referred_authority", "suspended"}

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _db_error(exc: Exception) -> HTTPException:
    if not os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or not os.environ.get(
        "SUPABASE_SERVICE_KEY"
    ):
        return HTTPException(
            status_code=503,
            detail="Database not configured — add credentials to .env.local",
        )
    return HTTPException(status_code=503, detail=f"Database error: {str(exc)}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _due_at(tier: int) -> str:
    hours = TIER_SLA_HOURS.get(tier, 48)
    due = datetime.now(timezone.utc) + timedelta(hours=hours)
    return due.isoformat()


def _require_internal_key(x_internal_key: Optional[str]) -> None:
    """Validate the x-internal-key header for admin-only routes."""
    expected = os.environ.get("INTERNAL_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Internal API key not configured — set INTERNAL_API_KEY in environment.",
        )
    if not x_internal_key or not secrets.compare_digest(x_internal_key, expected):
        raise HTTPException(
            status_code=403, detail="Forbidden. Invalid or missing internal API key."
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AssignReviewRequest(BaseModel):
    reviewer_id: str


class OutcomeRequest(BaseModel):
    outcome: str
    outcome_detail: str


class FlagRequest(BaseModel):
    listing_id: str
    flag_type: str  # "discriminatory" | "predatory"
    grounds: List[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    flagged_content: str


# ---------------------------------------------------------------------------
# GET /queue  (admin only)
# ---------------------------------------------------------------------------


@router.get("/queue")
async def get_review_queue(x_internal_key: Optional[str] = Header(None)):
    """
    List all open human reviews.
    Restricted to internal/admin access only.
    """
    _require_internal_key(x_internal_key)

    try:
        result = (
            _sb.table("human_reviews")
            .select("*")
            .eq("status", "open")
            .order("created_at")
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    reviews = result.data or []
    return {"total": len(reviews), "reviews": reviews}


# ---------------------------------------------------------------------------
# GET /{review_id}
# ---------------------------------------------------------------------------


@router.get("/{review_id}")
async def get_review(review_id: str):
    """Return full details for a single review."""
    try:
        result = (
            _sb.table("human_reviews")
            .select("*")
            .eq("id", review_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not result.data:
        raise HTTPException(status_code=404, detail="Review not found.")

    return result.data


# ---------------------------------------------------------------------------
# POST /{review_id}/assign
# ---------------------------------------------------------------------------


@router.post("/{review_id}/assign")
async def assign_review(review_id: str, body: AssignReviewRequest):
    """
    Assign a review to a reviewer.
    Sets assigned_at and calculates due_at based on the review tier.
    SLA: tier1=48h, tier2=5 business days, tier3=10 business days.
    """
    try:
        review_result = (
            _sb.table("human_reviews")
            .select("id, tier, status")
            .eq("id", review_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not review_result.data:
        raise HTTPException(status_code=404, detail="Review not found.")

    review = review_result.data
    if review.get("status") == "closed":
        raise HTTPException(
            status_code=409, detail="This review has already been closed."
        )

    tier = int(review.get("tier") or 1)
    now = _now()
    due = _due_at(tier)

    update_payload = {
        "reviewer_id": body.reviewer_id,
        "assigned_at": now,
        "due_at": due,
        "status": "in_progress",
        "updated_at": now,
    }

    try:
        result = (
            _sb.table("human_reviews")
            .update(update_payload)
            .eq("id", review_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    sla_hours = TIER_SLA_HOURS.get(tier, 48)
    return {
        "review_id": review_id,
        "reviewer_id": body.reviewer_id,
        "assigned_at": now,
        "due_at": due,
        "sla_hours": sla_hours,
        "review": result.data[0] if result.data else update_payload,
    }


# ---------------------------------------------------------------------------
# POST /{review_id}/outcome
# ---------------------------------------------------------------------------


@router.post("/{review_id}/outcome")
async def record_outcome(review_id: str, body: OutcomeRequest):
    """
    Record the outcome of a human review.

    'cleared'            → issue platform credit (credit_issued=True)
    'suspended'          → update subject's verification_status to 'suspended'
    'referred_authority' → create discrimination_flags entry if not already present
    'found_against'      → record outcome, no automatic action
    """
    if body.outcome not in VALID_OUTCOMES:
        raise HTTPException(
            status_code=422,
            detail=f"outcome must be one of: {sorted(VALID_OUTCOMES)}",
        )

    try:
        review_result = (
            _sb.table("human_reviews")
            .select("*")
            .eq("id", review_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not review_result.data:
        raise HTTPException(status_code=404, detail="Review not found.")

    review = review_result.data
    now = _now()

    update_payload = {
        "outcome": body.outcome,
        "outcome_detail": body.outcome_detail,
        "status": "closed",
        "closed_at": now,
        "updated_at": now,
        "credit_issued": False,
    }

    actions_taken = []

    # ------------------------------------------------------------------
    # Outcome: cleared — issue platform credit
    # ------------------------------------------------------------------
    if body.outcome == "cleared":
        update_payload["credit_issued"] = True
        subject_id = review.get("subject_id")
        subject_type = review.get("subject_type")

        # Record credit in the appropriate profile table
        if subject_id and subject_type:
            credit_record = {
                "id": str(uuid.uuid4()),
                "user_id": subject_id,
                "subject_type": subject_type,
                "review_id": review_id,
                "reason": "outcome_cleared",
                "issued_at": now,
            }
            try:
                _sb.table("platform_credits").insert(credit_record).execute()
                actions_taken.append("platform_credit_issued")
            except Exception:
                pass  # Non-fatal — outcome is still recorded

    # ------------------------------------------------------------------
    # Outcome: suspended — update subject's verification_status
    # ------------------------------------------------------------------
    elif body.outcome == "suspended":
        subject_id = review.get("subject_id")
        subject_type = review.get("subject_type")

        if subject_id and subject_type:
            profile_table = (
                "tenant_profiles" if subject_type == "tenant" else "landlord_profiles"
            )
            try:
                _sb.table(profile_table).update(
                    {"verification_status": "suspended", "updated_at": now}
                ).eq("user_id", subject_id).execute()
                actions_taken.append(
                    f"{profile_table}_verification_status_set_suspended"
                )
            except Exception as exc:
                raise _db_error(exc)

    # ------------------------------------------------------------------
    # Outcome: referred_authority — create discrimination_flags entry
    # ------------------------------------------------------------------
    elif body.outcome == "referred_authority":
        subject_id = review.get("subject_id")
        metadata = review.get("metadata") or {}
        listing_id = metadata.get("listing_id")

        # Check for an existing active flag before creating a duplicate
        existing_flag = None
        if listing_id:
            try:
                flag_check = (
                    _sb.table("discrimination_flags")
                    .select("id")
                    .eq("listing_id", listing_id)
                    .eq("active", True)
                    .limit(1)
                    .execute()
                )
                existing_flag = flag_check.data[0] if flag_check.data else None
            except Exception:
                pass

        if not existing_flag:
            flag_record = {
                "id": str(uuid.uuid4()),
                "listing_id": listing_id,
                "subject_id": subject_id,
                "flag_type": metadata.get("flag_type", "discriminatory"),
                "grounds": metadata.get("grounds", []),
                "source": "human_review_referral",
                "review_id": review_id,
                "outcome_detail": body.outcome_detail,
                "action": "referred_authority",
                "active": True,
                "created_at": now,
            }
            try:
                _sb.table("discrimination_flags").insert(flag_record).execute()
                actions_taken.append("discrimination_flag_created")
            except Exception as exc:
                raise _db_error(exc)
        else:
            actions_taken.append("discrimination_flag_already_exists")

    # Save outcome to review record
    try:
        result = (
            _sb.table("human_reviews")
            .update(update_payload)
            .eq("id", review_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    return {
        "review_id": review_id,
        "outcome": body.outcome,
        "actions_taken": actions_taken,
        "credit_issued": update_payload["credit_issued"],
        "review": result.data[0] if result.data else update_payload,
    }


# ---------------------------------------------------------------------------
# POST /flag
# ---------------------------------------------------------------------------


@router.post("/flag", status_code=201)
async def create_flag(body: FlagRequest):
    """
    Create a discrimination or predatory flag against a listing.

    Decision logic:
        confidence >= 0.85          → auto-ban: account banned, added to do_not_fly_list,
                                      listing set inactive
        confidence >= 0.60          → suspend listing + queue human_review tier=1 within 24h
        flag_type = 'predatory'     → mandatory law_enforcement referral regardless of
                                      confidence score (applied in addition to above actions)

    Returns the action taken.
    """
    valid_flag_types = {"discriminatory", "predatory"}
    if body.flag_type not in valid_flag_types:
        raise HTTPException(
            status_code=422,
            detail=f"flag_type must be one of: {sorted(valid_flag_types)}",
        )

    if not body.grounds:
        raise HTTPException(status_code=422, detail="grounds must not be empty.")

    now = _now()
    flag_id = str(uuid.uuid4())
    action = "flagged"
    actions_taken = []

    # ------------------------------------------------------------------
    # Fetch listing to get landlord_user_id
    # ------------------------------------------------------------------
    try:
        listing_result = (
            _sb.table("listings")
            .select("id, landlord_user_id, is_active")
            .eq("id", body.listing_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not listing_result.data:
        raise HTTPException(status_code=404, detail="Listing not found.")

    listing = listing_result.data
    landlord_user_id = listing.get("landlord_user_id")

    # ------------------------------------------------------------------
    # High confidence (>= 0.85): auto-ban
    # ------------------------------------------------------------------
    if body.confidence_score >= 0.85:
        action = "account_banned"

        # Ban the landlord account
        if landlord_user_id:
            try:
                _sb.table("landlord_profiles").update(
                    {"verification_status": "banned", "updated_at": now}
                ).eq("user_id", landlord_user_id).execute()
                actions_taken.append("landlord_account_banned")
            except Exception as exc:
                raise _db_error(exc)

            # Add to do_not_fly_list
            try:
                _sb.table("do_not_fly_list").insert(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": landlord_user_id,
                        "reason": f"auto_ban_flag_{flag_id}",
                        "flag_id": flag_id,
                        "created_at": now,
                    }
                ).execute()
                actions_taken.append("added_to_do_not_fly_list")
            except Exception as exc:
                raise _db_error(exc)

        # Deactivate listing
        try:
            _sb.table("listings").update({"is_active": False, "updated_at": now}).eq(
                "id", body.listing_id
            ).execute()
            actions_taken.append("listing_deactivated")
        except Exception as exc:
            raise _db_error(exc)

    # ------------------------------------------------------------------
    # Moderate confidence (>= 0.60): suspend listing + queue human review
    # ------------------------------------------------------------------
    elif body.confidence_score >= 0.60:
        action = "listing_suspended_pending_review"

        # Suspend the listing
        try:
            _sb.table("listings").update(
                {"is_active": False, "is_suspended": True, "updated_at": now}
            ).eq("id", body.listing_id).execute()
            actions_taken.append("listing_suspended")
        except Exception as exc:
            raise _db_error(exc)

        # Queue human review — tier 1, 24h priority
        try:
            _sb.table("human_reviews").insert(
                {
                    "id": str(uuid.uuid4()),
                    "subject_type": "listing",
                    "subject_id": body.listing_id,
                    "review_type": f"flag_{body.flag_type}",
                    "tier": 1,
                    "status": "open",
                    "priority_hours": 24,
                    "metadata": {
                        "flag_id": flag_id,
                        "listing_id": body.listing_id,
                        "landlord_user_id": landlord_user_id,
                        "flag_type": body.flag_type,
                        "grounds": body.grounds,
                        "confidence_score": body.confidence_score,
                        "flagged_content": body.flagged_content,
                    },
                    "created_at": now,
                }
            ).execute()
            actions_taken.append("human_review_queued_24h")
        except Exception as exc:
            raise _db_error(exc)

    # ------------------------------------------------------------------
    # Predatory flag: mandatory law enforcement referral (always)
    # ------------------------------------------------------------------
    law_enforcement_referral = False
    if body.flag_type == "predatory":
        law_enforcement_referral = True
        try:
            _sb.table("law_enforcement_referrals").insert(
                {
                    "id": str(uuid.uuid4()),
                    "flag_id": flag_id,
                    "listing_id": body.listing_id,
                    "landlord_user_id": landlord_user_id,
                    "grounds": body.grounds,
                    "flagged_content": body.flagged_content,
                    "confidence_score": body.confidence_score,
                    "referral_status": "pending",
                    "created_at": now,
                }
            ).execute()
            actions_taken.append("law_enforcement_referral_created")
        except Exception as exc:
            raise _db_error(exc)

    # ------------------------------------------------------------------
    # Save the flag record
    # ------------------------------------------------------------------
    flag_record = {
        "id": flag_id,
        "listing_id": body.listing_id,
        "subject_id": landlord_user_id,
        "flag_type": body.flag_type,
        "grounds": body.grounds,
        "confidence_score": body.confidence_score,
        "flagged_content": body.flagged_content,
        "action": action,
        "active": True,
        "law_enforcement_referral": law_enforcement_referral,
        "created_at": now,
    }

    try:
        result = _sb.table("discrimination_flags").insert(flag_record).execute()
    except Exception as exc:
        raise _db_error(exc)

    return {
        "flag_id": flag_id,
        "listing_id": body.listing_id,
        "flag_type": body.flag_type,
        "confidence_score": body.confidence_score,
        "action": action,
        "actions_taken": actions_taken,
        "law_enforcement_referral": law_enforcement_referral,
        "flag": result.data[0] if result.data else flag_record,
    }

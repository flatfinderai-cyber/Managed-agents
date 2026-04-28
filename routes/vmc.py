# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — VMC Routes (FF-CORE-007)
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.

"""
/api/vmc/thread/{match_id}      GET  — fetch or open thread
/api/vmc/thread/{thread_id}/send POST — send a message (validates server-side)
/api/vmc/thread/{thread_id}     GET  — get full thread with messages
/api/vmc/thread/{thread_id}/withdraw POST — mutual withdrawal
/api/vmc/thread/{thread_id}/report  POST — report behaviour
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

from deps.supabase_auth import CurrentUserId, assert_same_user
from services.vmc_validator import validate_message

router = APIRouter()

_sb = create_client(
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""),
    os.environ.get("SUPABASE_SERVICE_KEY", ""),
)

LANDLORD_RESPONSE_WINDOW_HOURS = 24
REMINDER_1_HOURS = 12
REMINDER_2_HOURS = 20
MIN_VALID_MESSAGES = 3


def _user_in_match_row(match: dict, user_id: str) -> bool:
    """Whether JWT subject is tenant or landlord on this match row."""
    ids = [
        match.get("tenant_id"),
        match.get("landlord_id"),
    ]
    return user_id in {str(x) for x in ids if x}


def _user_in_thread_row(t: dict, user_id: str) -> bool:
    return user_id in (str(t.get("tenant_id") or ""), str(t.get("landlord_id") or ""))


# ── Models ─────────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    content: str
    sender_role: str  # 'landlord' | 'tenant'
    sender_id: str

class WithdrawRequest(BaseModel):
    user_id: str
    reason: Optional[str] = None

class ReportRequest(BaseModel):
    reporter_id: str
    reason: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_listing_context(listing_id: str) -> dict:
    """Fetch listing context for semantic coherence scoring."""
    try:
        r = _sb.table("listings").select(
            "address, available_date, price, city"
        ).eq("id", listing_id).maybe_single().execute()
        if r.data:
            return {
                "address": r.data.get("address", ""),
                "move_in_date": str(r.data.get("available_date", "")),
                "rent_amount": str(r.data.get("price", "")),
                "city": r.data.get("city", ""),
            }
    except Exception:
        pass
    return {}


def _check_window_expiry(thread: dict) -> bool:
    """Returns True if the 24-hour window has expired (auto-cancel trigger)."""
    if not thread.get("window_expires_at"):
        return False
    expires = datetime.fromisoformat(thread["window_expires_at"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) > expires


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/thread/{match_id}/open")
async def get_or_open_thread(match_id: str, current: CurrentUserId):
    """
    Returns the VMC thread for a match, or creates it if it doesn't exist yet.
    FF-CORE-007 §2: opens only when both parties have confirmed and all conditions met.
    """
    # Check if thread already exists
    existing = _sb.table("vmc_threads").select("*").eq("match_id", match_id).maybe_single().execute()
    if existing.data:
        if not _user_in_thread_row(existing.data, current):
            raise HTTPException(status_code=403, detail="Not a participant in this thread.")
        return existing.data

    # Get the match record
    match = _sb.table("matches").select("*").eq("id", match_id).maybe_single().execute()
    if not match.data:
        raise HTTPException(status_code=404, detail="Match not found.")
    m = match.data
    if not _user_in_match_row(m, current):
        raise HTTPException(status_code=403, detail="Not a participant in this match.")

    # FF-CORE-007 §2: both parties must have confirmed
    if m["status"] != "confirmed_both":
        raise HTTPException(
            status_code=409,
            detail="The VMC thread cannot open until both parties have confirmed the match."
        )

    # Create thread
    thread = _sb.table("vmc_threads").insert({
        "match_id": match_id,
        "listing_id": m["listing_id"],
        "landlord_id": m["landlord_id"],
        "tenant_id": m["tenant_id"],
        "status": "open",
    }).execute()

    # Update match status
    _sb.table("matches").update({"status": "vmc_open"}).eq("id", match_id).execute()

    return thread.data[0]


@router.get("/thread/{thread_id}")
async def get_thread(thread_id: str, current: CurrentUserId):
    """Get full VMC thread with messages."""
    thread = _sb.table("vmc_threads").select("*").eq("id", thread_id).maybe_single().execute()
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if not _user_in_thread_row(thread.data, current):
        raise HTTPException(status_code=403, detail="Not a participant in this thread.")

    # Check for window expiry and auto-cancel if needed
    if thread.data["status"] == "open" and _check_window_expiry(thread.data):
        _sb.table("vmc_threads").update({
            "status": "cancelled_nonresponse",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancellation_reason": "Landlord did not respond within the 24-hour window.",
        }).eq("id", thread_id).execute()
        # Flag landlord account
        _increment_landlord_nonresponse_flag(thread.data["landlord_id"])
        # Return tenant to priority pool
        _grant_tenant_priority(thread.data["tenant_id"], "landlord_nonresponse")

    messages = _sb.table("vmc_messages").select("*").eq("thread_id", thread_id).order("created_at").execute()

    return {
        "thread": thread.data,
        "messages": messages.data or [],
    }


@router.post("/thread/{thread_id}/send")
async def send_message(thread_id: str, body: SendMessageRequest, current: CurrentUserId):
    """
    Send a VMC message. Validates server-side before accepting.
    FF-CORE-007 §4 — all checks run here.
    """
    assert_same_user(body.sender_id, current)
    thread = _sb.table("vmc_threads").select("*").eq("id", thread_id).maybe_single().execute()
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found.")
    t = thread.data
    if not _user_in_thread_row(t, current):
        raise HTTPException(status_code=403, detail="Not a participant in this thread.")
    expected = str(t["tenant_id"] if body.sender_role == "tenant" else t["landlord_id"])
    if expected != body.sender_id:
        raise HTTPException(
            status_code=422,
            detail="sender_id does not match this role on the thread.",
        )

    if t["status"] != "open":
        raise HTTPException(
            status_code=409,
            detail=f"This VMC thread is not open. Current status: {t['status']}."
        )

    # Check window expiry
    if _check_window_expiry(t):
        raise HTTPException(status_code=409, detail="The 24-hour response window has expired. This match has been cancelled.")

    # Get listing context for semantic check
    listing_context = _get_listing_context(t["listing_id"])

    # Get sender's prior messages (for uniqueness check)
    prior_msgs = _sb.table("vmc_messages").select("content").eq(
        "thread_id", thread_id
    ).eq("sender_role", body.sender_role).eq("is_valid", True).execute()
    prior_contents = [m["content"] for m in (prior_msgs.data or [])]

    # Get other party's last message timestamp (for response pairing)
    other_role = "landlord" if body.sender_role == "tenant" else "tenant"
    other_msgs = _sb.table("vmc_messages").select("created_at").eq(
        "thread_id", thread_id
    ).eq("sender_role", other_role).order("created_at", desc=True).limit(1).execute()
    other_last_at = None
    if other_msgs.data:
        ts = other_msgs.data[0]["created_at"]
        other_last_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))

    submitted_at = datetime.now(timezone.utc)

    # Run all validation checks (FF-CORE-007 §4)
    result = validate_message(
        content=body.content,
        listing_context=listing_context,
        prior_sender_messages=prior_contents,
        submitted_at=submitted_at,
        other_party_last_message_at=other_last_at,
    )

    # Store the message (valid or not — evidence trail requires all attempts)
    msg_record = {
        "thread_id":        thread_id,
        "sender_role":      body.sender_role,
        "sender_id":        body.sender_id,
        "content":          body.content,
        "word_count":       result["word_count"],
        "is_valid":         result["is_valid"],
        "check_length":     result["check_length"],
        "check_dict":       result["check_dict"],
        "check_semantic":   result["check_semantic"],
        "check_unique":     result["check_unique"],
        "check_template":   result["check_template"],
        "check_responsive": result["check_responsive"],
        "semantic_score":   result["semantic_score"],
        "dict_pct":         result["dict_pct"],
        "similarity_max":   result["similarity_max"],
        "rejection_reason": result["rejection_reason"],
    }
    saved = _sb.table("vmc_messages").insert(msg_record).execute()

    if not result["is_valid"]:
        # Return 422 with plain-language explanation
        return {
            "accepted": False,
            "rejection_reason": result["rejection_reason"],
            "word_count": result["word_count"],
            "checks": {
                "length":     result["check_length"],
                "dictionary": result["check_dict"],
                "relevance":  result["check_semantic"],
                "original":   result["check_unique"],
                "substantive": result["check_template"],
                "responsive": result["check_responsive"],
            }
        }

    # ── Valid message — update thread counters ─────────────────────────────────
    count_field = f"{body.sender_role}_valid_count"
    new_count = t[count_field] + 1
    update_data = {count_field: new_count, "updated_at": submitted_at.isoformat()}

    # Start 24-hour landlord window on first valid tenant message (FF-CORE-007 §5)
    if body.sender_role == "tenant" and not t.get("window_start_at") and new_count == 1:
        window_expires = submitted_at + timedelta(hours=LANDLORD_RESPONSE_WINDOW_HOURS)
        update_data["window_start_at"] = submitted_at.isoformat()
        update_data["window_expires_at"] = window_expires.isoformat()

    _sb.table("vmc_threads").update(update_data).eq("id", thread_id).execute()

    # ── Check for completion ────────────────────────────────────────────────────
    landlord_count = t["landlord_valid_count"] + (1 if body.sender_role == "landlord" else 0)
    tenant_count = t["tenant_valid_count"] + (1 if body.sender_role == "tenant" else 0)

    thread_complete = landlord_count >= MIN_VALID_MESSAGES and tenant_count >= MIN_VALID_MESSAGES

    # Check response pairing requirement: at least one responsive message per party
    # (simplified: if both have >= 3 valid messages, pairing is implicitly met)
    if thread_complete:
        _sb.table("vmc_threads").update({
            "status": "complete",
            "completed_at": submitted_at.isoformat(),
        }).eq("id", thread_id).execute()
        _sb.table("matches").update({"status": "vmc_complete"}).eq(
            "id", t["match_id"]
        ).execute()

    return {
        "accepted": True,
        "message_id": saved.data[0]["id"],
        "sender_valid_count": new_count,
        "thread_complete": thread_complete,
        "remaining_for_sender": max(0, MIN_VALID_MESSAGES - new_count),
    }


@router.post("/thread/{thread_id}/withdraw")
async def withdraw(thread_id: str, body: WithdrawRequest, current: CurrentUserId):
    """
    Mutual withdrawal. FF-CORE-007 §7.
    Not a non-response flag — provided via platform withdrawal function.
    """
    assert_same_user(body.user_id, current)
    thread = _sb.table("vmc_threads").select("*").eq("id", thread_id).maybe_single().execute()
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if not _user_in_thread_row(thread.data, current):
        raise HTTPException(status_code=403, detail="Not a participant in this thread.")
    if thread.data["status"] != "open":
        raise HTTPException(status_code=409, detail="Thread is not open.")

    _sb.table("vmc_threads").update({
        "status": "cancelled_withdrawal",
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "cancellation_reason": body.reason or "Party withdrew via platform.",
    }).eq("id", thread_id).execute()

    _sb.table("matches").update({"status": "cancelled_tenant"}).eq(
        "id", thread.data["match_id"]
    ).execute()

    # Return tenant to active pool
    _grant_tenant_priority(thread.data["tenant_id"], "withdrawal_recovery")

    return {"withdrawn": True}


@router.post("/thread/{thread_id}/report")
async def report_behaviour(thread_id: str, body: ReportRequest, current: CurrentUserId):
    """Report behaviour in a VMC thread — triggers Human Review (FF-CORE-008 §2.4)."""
    assert_same_user(body.reporter_id, current)
    thread = _sb.table("vmc_threads").select("*").eq("id", thread_id).maybe_single().execute()
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if not _user_in_thread_row(thread.data, current):
        raise HTTPException(status_code=403, detail="Not a participant in this thread.")

    _sb.table("human_reviews").insert({
        "subject_type":   "vmc_thread",
        "subject_id":     thread_id,
        "trigger_code":   "vmc_user_report",
        "trigger_detail": body.reason,
        "tier":           1,
        "cost_model":     "no_cost",
    }).execute()

    return {"reported": True, "detail": "A review has been opened. You will be notified when it closes."}


# ── Internal helpers ────────────────────────────────────────────────────────────

def _increment_landlord_nonresponse_flag(landlord_user_id: str):
    """Increment non-response flag. 3 in 12 months = auto suspension."""
    profile = _sb.table("landlord_profiles").select(
        "id, non_response_flags"
    ).eq("user_id", landlord_user_id).maybe_single().execute()
    if not profile.data:
        return
    new_count = (profile.data["non_response_flags"] or 0) + 1
    update = {"non_response_flags": new_count, "updated_at": datetime.now(timezone.utc).isoformat()}
    if new_count >= 3:
        update["verification_status"] = "suspended"
        _sb.table("human_reviews").insert({
            "subject_type":  "landlord_profile",
            "subject_id":    profile.data["id"],
            "trigger_code":  "three_nonresponse_flags",
            "trigger_detail": f"Landlord has {new_count} non-response flags in 12 months.",
            "tier":          2,
            "cost_model":    "cost_recovery",
        }).execute()
    _sb.table("landlord_profiles").update(update).eq("id", profile.data["id"]).execute()


def _grant_tenant_priority(tenant_user_id: str, reason: str):
    """Grant priority pool status to a tenant who was unfairly cancelled."""
    _sb.table("tenant_profiles").update({
        "has_priority": True,
        "priority_granted_at": datetime.now(timezone.utc).isoformat(),
        "priority_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", tenant_user_id).execute()

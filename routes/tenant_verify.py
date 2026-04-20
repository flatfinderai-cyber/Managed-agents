# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — tenant_verify.py
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.
#
# FF-CORE-009: Tenant Verification — 6-Tier Documentation Framework
# RULES:
#   - Credit score is NEVER a gate. No credit score field exists.
#   - SIN (Social Insurance Number) is NEVER requested.
#   - Identity documents cannot be requested before match confirmation.
#   - All 6 tiers are equally valid. No tier weighting is visible to landlords.

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

from deps.supabase_auth import CurrentUserId, assert_same_user

router = APIRouter(tags=["Tenant Verification"])

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

VALID_DOC_TYPES = {
    "bank_statement_3mo",
    "employment_contract",
    "payslip",
    "noa",
    "accountant_letter",
    "pension_statement",
    "investment_statement",
    "alternative_documentation",
}

# Tiers that can be verified automatically vs. those requiring human review
AUTO_VERIFY_TIERS = {1, 2}
HUMAN_REVIEW_TIERS = {3, 4, 5, 6}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TenantProfileCreate(BaseModel):
    user_id: str
    full_name: Optional[str] = None
    preferred_contact_email: Optional[str] = None
    preferred_contact_phone: Optional[str] = None
    # Search preferences
    desired_cities: Optional[List[str]] = None
    desired_property_types: Optional[List[str]] = None
    desired_move_in_from: Optional[str] = None   # ISO date string
    desired_move_in_to: Optional[str] = None     # ISO date string
    max_rent_cents: Optional[int] = None
    non_negotiables: Optional[dict] = None


class DocumentUpload(BaseModel):
    storage_path: str
    doc_type: str
    tier: int
    # Optional metadata
    statement_month: Optional[str] = None       # e.g. "2024-01" for bank statements
    net_monthly_income_cents: Optional[int] = None  # supplied by tenant for tier-2 payslip/NOA
    reserve_ratio: Optional[float] = None       # supplied for tier-1 bank statement check


class VerifyTierRequest(BaseModel):
    tier: int


class SearchPreferences(BaseModel):
    desired_cities: Optional[List[str]] = None
    desired_property_types: Optional[List[str]] = None
    desired_move_in_from: Optional[str] = None
    desired_move_in_to: Optional[str] = None
    max_rent_cents: Optional[int] = None
    non_negotiables: Optional[dict] = None


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _db_error(exc: Exception) -> HTTPException:
    """Convert a Supabase / network exception into a 503."""
    msg = str(exc)
    if not os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"):
        return HTTPException(
            status_code=503,
            detail="Database not configured — add credentials to .env.local",
        )
    return HTTPException(status_code=503, detail=f"Database error: {msg}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _queue_human_review(
    subject_type: str,
    subject_id: str,
    review_type: str,
    tier: int,
    metadata: Optional[dict] = None,
) -> None:
    """Insert a human_reviews row. Non-fatal — swallow exceptions so main flow proceeds."""
    try:
        _sb.table("human_reviews").insert(
            {
                "id": str(uuid.uuid4()),
                "subject_type": subject_type,
                "subject_id": subject_id,
                "review_type": review_type,
                "tier": tier,
                "status": "open",
                "metadata": metadata or {},
                "created_at": _now(),
            }
        ).execute()
    except Exception:
        pass  # Review queue failure must not block the user-facing response


# ---------------------------------------------------------------------------
# GET /profile/{user_id}
# ---------------------------------------------------------------------------


@router.get("/profile/{user_id}")
async def get_tenant_profile(user_id: str, current: CurrentUserId):
    """
    Return the tenant profile and their current verification status.
    No credit score field is returned; no SIN is stored or surfaced.
    """
    assert_same_user(user_id, current)
    try:
        result = (
            _sb.table("tenant_profiles")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not result.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")

    return result.data


# ---------------------------------------------------------------------------
# POST /profile
# ---------------------------------------------------------------------------


@router.post("/profile", status_code=201)
async def create_or_update_tenant_profile(body: TenantProfileCreate, current: CurrentUserId):
    """
    Create or update a tenant profile.
    Stores search preferences and non-negotiables.
    Credit score is never a field. SIN is never requested.
    """
    assert_same_user(body.user_id, current)
    try:
        existing = (
            _sb.table("tenant_profiles")
            .select("id")
            .eq("user_id", body.user_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    payload = {
        "user_id": body.user_id,
        "full_name": body.full_name,
        "preferred_contact_email": body.preferred_contact_email,
        "preferred_contact_phone": body.preferred_contact_phone,
        "desired_cities": body.desired_cities,
        "desired_property_types": body.desired_property_types,
        "desired_move_in_from": body.desired_move_in_from,
        "desired_move_in_to": body.desired_move_in_to,
        "max_rent_cents": body.max_rent_cents,
        "non_negotiables": body.non_negotiables,
        "updated_at": _now(),
    }

    try:
        if existing.data:
            record_id = existing.data[0]["id"]
            result = (
                _sb.table("tenant_profiles")
                .update(payload)
                .eq("id", record_id)
                .execute()
            )
            return {"action": "updated", "profile": result.data[0] if result.data else payload}
        else:
            payload["id"] = str(uuid.uuid4())
            payload["created_at"] = _now()
            payload["verification_status"] = "unverified"
            result = _sb.table("tenant_profiles").insert(payload).execute()
            return {"action": "created", "profile": result.data[0] if result.data else payload}
    except Exception as exc:
        raise _db_error(exc)


# ---------------------------------------------------------------------------
# GET /profile/{user_id}/documents
# ---------------------------------------------------------------------------


@router.get("/profile/{user_id}/documents")
async def list_tenant_documents(user_id: str, current: CurrentUserId):
    """List all documents uploaded by this tenant, grouped by tier."""
    assert_same_user(user_id, current)
    try:
        result = (
            _sb.table("tenant_documents")
            .select("*")
            .eq("user_id", user_id)
            .order("tier")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    documents = result.data or []

    # Group by tier for a cleaner response
    grouped: dict = {}
    for doc in documents:
        tier_key = f"tier_{doc['tier']}"
        grouped.setdefault(tier_key, []).append(doc)

    return {"user_id": user_id, "total": len(documents), "by_tier": grouped}


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/documents
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/documents", status_code=201)
async def upload_document_reference(user_id: str, body: DocumentUpload, current: CurrentUserId):
    """
    Record a reference to a document already uploaded to storage.
    Identity documents (passport, driver's licence, etc.) are not accepted
    here — those are handled post-match-confirmation only.
    """
    assert_same_user(user_id, current)
    if body.doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid doc_type '{body.doc_type}'. "
                f"Accepted values: {sorted(VALID_DOC_TYPES)}"
            ),
        )

    if not (1 <= body.tier <= 6):
        raise HTTPException(status_code=422, detail="tier must be between 1 and 6.")

    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "storage_path": body.storage_path,
        "doc_type": body.doc_type,
        "tier": body.tier,
        "statement_month": body.statement_month,
        "net_monthly_income_cents": body.net_monthly_income_cents,
        "reserve_ratio": body.reserve_ratio,
        "review_status": "pending",
        "created_at": _now(),
    }

    try:
        result = _sb.table("tenant_documents").insert(record).execute()
    except Exception as exc:
        raise _db_error(exc)

    return {
        "message": "Document reference recorded.",
        "document": result.data[0] if result.data else record,
    }


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/verify
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/verify")
async def trigger_verification(user_id: str, body: VerifyTierRequest, current: CurrentUserId):
    """
    Trigger verification for the given tier.

    Tier 1 (Bank Statements — 3 months):
        Automated check — all 3 bank statement documents must have
        reserve_ratio >= 6.0. Passes automatically if condition met;
        queues human review if not.

    Tier 2 (Employment Contract / Payslip / NOA):
        Automated check — net_monthly_income_cents must be present on
        at least one submitted document. Passes automatically if present;
        queues human review if missing.

    Tiers 3–6:
        No automated checks available. Queues a human_reviews row with
        tier=1 (48-hour SLA) immediately.

    Credit score is NEVER evaluated. SIN is NEVER referenced.
    All 6 tiers are equally valid — no weighting is applied.
    """
    assert_same_user(user_id, current)
    tier = body.tier
    if not (1 <= tier <= 6):
        raise HTTPException(status_code=422, detail="tier must be between 1 and 6.")

    # Confirm profile exists
    try:
        profile_result = (
            _sb.table("tenant_profiles")
            .select("id, verification_status")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not profile_result.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")

    profile_id = profile_result.data["id"]

    # -----------------------------------------------------------------------
    # Tier 1: Reserve ratio check across all 3 bank statements
    # -----------------------------------------------------------------------
    if tier == 1:
        try:
            docs_result = (
                _sb.table("tenant_documents")
                .select("id, doc_type, reserve_ratio")
                .eq("user_id", user_id)
                .eq("tier", 1)
                .eq("doc_type", "bank_statement_3mo")
                .execute()
            )
        except Exception as exc:
            raise _db_error(exc)

        docs = docs_result.data or []
        if len(docs) < 3:
            _queue_human_review(
                subject_type="tenant",
                subject_id=user_id,
                review_type="tier1_bank_statement_insufficient_docs",
                tier=1,
                metadata={"docs_submitted": len(docs), "docs_required": 3},
            )
            return {
                "tier": 1,
                "result": "review_queued",
                "reason": (
                    f"Only {len(docs)} of 3 required bank statements submitted. "
                    "A reviewer will follow up within 48 hours."
                ),
            }

        failing = [d for d in docs if (d.get("reserve_ratio") or 0) < 6.0]
        if failing:
            _queue_human_review(
                subject_type="tenant",
                subject_id=user_id,
                review_type="tier1_bank_statement_reserve_ratio_below_threshold",
                tier=1,
                metadata={"failing_document_ids": [d["id"] for d in failing]},
            )
            return {
                "tier": 1,
                "result": "review_queued",
                "reason": (
                    "One or more bank statements have a reserve ratio below 6.0. "
                    "A reviewer will follow up within 48 hours."
                ),
            }

        # Auto-pass
        try:
            _sb.table("tenant_profiles").update(
                {"tier1_status": "verified", "updated_at": _now()}
            ).eq("id", profile_id).execute()
        except Exception as exc:
            raise _db_error(exc)

        return {"tier": 1, "result": "verified", "reason": "All bank statements meet the reserve ratio requirement."}

    # -----------------------------------------------------------------------
    # Tier 2: Net monthly income check
    # -----------------------------------------------------------------------
    elif tier == 2:
        try:
            docs_result = (
                _sb.table("tenant_documents")
                .select("id, doc_type, net_monthly_income_cents")
                .eq("user_id", user_id)
                .eq("tier", 2)
                .execute()
            )
        except Exception as exc:
            raise _db_error(exc)

        docs = docs_result.data or []
        income_docs = [
            d for d in docs
            if d.get("net_monthly_income_cents") is not None and d["net_monthly_income_cents"] > 0
        ]

        if not income_docs:
            _queue_human_review(
                subject_type="tenant",
                subject_id=user_id,
                review_type="tier2_income_not_present",
                tier=1,
                metadata={"docs_submitted": len(docs)},
            )
            return {
                "tier": 2,
                "result": "review_queued",
                "reason": (
                    "Net monthly income could not be confirmed from submitted documents. "
                    "A reviewer will follow up within 48 hours."
                ),
            }

        # Auto-pass
        try:
            _sb.table("tenant_profiles").update(
                {"tier2_status": "verified", "updated_at": _now()}
            ).eq("id", profile_id).execute()
        except Exception as exc:
            raise _db_error(exc)

        return {"tier": 2, "result": "verified", "reason": "Net monthly income confirmed."}

    # -----------------------------------------------------------------------
    # Tiers 3–6: Human review required
    # -----------------------------------------------------------------------
    else:
        tier_label_map = {
            3: "accountant_letter",
            4: "pension_or_investment",
            5: "alternative_documentation",
            6: "additional_alternative",
        }
        _queue_human_review(
            subject_type="tenant",
            subject_id=user_id,
            review_type=f"tier{tier}_{tier_label_map.get(tier, 'manual')}",
            tier=1,
            metadata={"documentation_tier": tier},
        )
        return {
            "tier": tier,
            "result": "review_queued",
            "reason": (
                f"Tier {tier} documentation has been queued for human review. "
                "A reviewer will follow up within 48 hours."
            ),
        }


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/preferences
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/preferences")
async def save_search_preferences(user_id: str, body: SearchPreferences, current: CurrentUserId):
    """Save or update search preferences for a tenant profile."""
    assert_same_user(user_id, current)
    try:
        existing = (
            _sb.table("tenant_profiles")
            .select("id")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if not existing.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")

    profile_id = existing.data["id"]
    update_payload = {
        "desired_cities": body.desired_cities,
        "desired_property_types": body.desired_property_types,
        "desired_move_in_from": body.desired_move_in_from,
        "desired_move_in_to": body.desired_move_in_to,
        "max_rent_cents": body.max_rent_cents,
        "non_negotiables": body.non_negotiables,
        "updated_at": _now(),
    }
    # Remove None values to avoid overwriting existing preferences with nulls
    update_payload = {k: v for k, v in update_payload.items() if v is not None or k == "updated_at"}

    try:
        result = (
            _sb.table("tenant_profiles")
            .update(update_payload)
            .eq("id", profile_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    return {
        "message": "Search preferences saved.",
        "profile": result.data[0] if result.data else update_payload,
    }

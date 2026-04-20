# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — landlord_verify.py
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.
#
# FF-CORE-010: Landlord Verification — 5 Sequential Forms
# CRITICAL RULE (Form 2):
#   "No listing is published on the basis of an agent's authority alone.
#    The registered owner is always contacted."
# Forms must be submitted in order (1 → 2 → 3 → 4 → 5).
# Return HTTP 409 if a prior form has not been verified.

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

from deps.supabase_auth import CurrentUserId, assert_same_user

router = APIRouter(tags=["Landlord Verification"])

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


def _queue_human_review(
    subject_type: str,
    subject_id: str,
    review_type: str,
    tier: int,
    priority_hours: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Insert a human_reviews row. Non-fatal."""
    try:
        record = {
            "id": str(uuid.uuid4()),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "review_type": review_type,
            "tier": tier,
            "status": "open",
            "metadata": metadata or {},
            "created_at": _now(),
        }
        if priority_hours:
            record["priority_hours"] = priority_hours
        _sb.table("human_reviews").insert(record).execute()
    except Exception:
        pass


def _get_profile(user_id: str) -> dict:
    """Fetch landlord profile or raise 404."""
    try:
        result = (
            _sb.table("landlord_profiles")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)
    if not result.data:
        raise HTTPException(status_code=404, detail="Landlord profile not found.")
    return result.data


def _require_prior_form(profile: dict, required_status_field: str, form_number: int) -> None:
    """Raise 409 if the preceding form has not been verified."""
    status = profile.get(required_status_field)
    if status != "verified":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Form {form_number - 1} must be verified before submitting Form {form_number}. "
                f"Current status of Form {form_number - 1}: '{status or 'pending'}'."
            ),
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LandlordProfileCreate(BaseModel):
    user_id: str
    trading_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class Form1KYC(BaseModel):
    full_legal_name: str
    date_of_birth: str                          # ISO date string
    gov_id_type: str
    gov_id_storage_path: str
    residential_address: dict                   # JSONB
    address_proof_storage_path: str
    primary_phone: str
    primary_email: str
    tribunal_decisions_declaration: bool
    tribunal_details: Optional[str] = None
    licence_revoked_declaration: bool
    licence_revoked_details: Optional[str] = None


class Form2Authority(BaseModel):
    authority_type: str                         # owner | agent_with_authority | property_manager
    title_deed_storage_path: Optional[str] = None
    registered_owner_name: str
    authority_letter_storage_path: Optional[str] = None
    owner_contact_phone: str
    owner_contact_email: str


class Form3Municipal(BaseModel):
    building_permit_status: str
    is_legal_dwelling: bool
    legal_dwelling_confirmation: Optional[str] = None
    outstanding_orders: bool
    outstanding_orders_detail: Optional[str] = None
    zoning_classification: str
    is_residential_zoned: bool
    is_secondary_suite: bool
    is_legal_secondary_suite: Optional[bool] = None


class Form4History(BaseModel):
    last_inspection_date: str                   # ISO date string
    inspector_name: str
    inspector_licence: str
    known_deficiencies: Optional[str] = None
    active_construction_building: bool
    active_construction_adjacent: bool
    construction_detail: Optional[str] = None
    water_damage_36mo: bool
    water_damage_detail: Optional[str] = None
    mould_48mo: bool
    mould_detail: Optional[str] = None
    mould_clearance_confirmed: Optional[bool] = None
    pest_24mo: bool
    pest_detail: Optional[str] = None
    insurance_claims_36mo: bool
    insurance_claims_detail: Optional[str] = None
    utility_providers: Optional[dict] = None
    utility_consumption_averages: Optional[dict] = None


class Form5Agreement(BaseModel):
    agreed_terms_of_service: bool
    agreed_fair_housing: bool
    agreed_no_discriminatory_screening: bool
    agreed_owner_contact_obligation: bool
    agreed_deposit_protection: bool
    deposit_protection_scheme_name: str
    deposit_protection_scheme_ref: str
    signatory_name: str


# ---------------------------------------------------------------------------
# GET /profile/{user_id}
# ---------------------------------------------------------------------------


@router.get("/profile/{user_id}")
async def get_landlord_profile(user_id: str, current: CurrentUserId):
    """Return the landlord profile and all 5 form statuses."""
    assert_same_user(user_id, current)
    return _get_profile(user_id)


# ---------------------------------------------------------------------------
# POST /profile
# ---------------------------------------------------------------------------


@router.post("/profile", status_code=201)
async def create_landlord_profile(body: LandlordProfileCreate, current: CurrentUserId):
    """
    Create a landlord profile.
    All 5 form statuses are initialised as 'pending'.
    """
    assert_same_user(body.user_id, current)
    try:
        existing = (
            _sb.table("landlord_profiles")
            .select("id")
            .eq("user_id", body.user_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="A landlord profile already exists for this user. Use PATCH to update.",
        )

    payload = {
        "id": str(uuid.uuid4()),
        "user_id": body.user_id,
        "trading_name": body.trading_name,
        "contact_email": body.contact_email,
        "contact_phone": body.contact_phone,
        # All form statuses initialised as pending
        "form1_kyc_status": "pending",
        "form2_authority_status": "pending",
        "form3_municipal_status": "pending",
        "form4_history_status": "pending",
        "form5_agreement_status": "pending",
        "verification_status": "pending",
        "crown_verification_status": "pending",
        "owner_contact_confirmed": False,
        "created_at": _now(),
        "updated_at": _now(),
    }

    try:
        result = _sb.table("landlord_profiles").insert(payload).execute()
    except Exception as exc:
        raise _db_error(exc)

    return {"action": "created", "profile": result.data[0] if result.data else payload}


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/form1  — KYC
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/form1")
async def submit_form1_kyc(user_id: str, body: Form1KYC, current: CurrentUserId):
    """
    Submit KYC form.
    Automated identity check: if full_legal_name and date_of_birth are present,
    the record is marked 'verified'. Otherwise queued for human review.
    """
    assert_same_user(user_id, current)
    profile = _get_profile(user_id)
    profile_id = profile["id"]

    form_data = {
        "form1_full_legal_name": body.full_legal_name,
        "form1_date_of_birth": body.date_of_birth,
        "form1_gov_id_type": body.gov_id_type,
        "form1_gov_id_storage_path": body.gov_id_storage_path,
        "form1_residential_address": body.residential_address,
        "form1_address_proof_storage_path": body.address_proof_storage_path,
        "form1_primary_phone": body.primary_phone,
        "form1_primary_email": body.primary_email,
        "form1_tribunal_decisions_declaration": body.tribunal_decisions_declaration,
        "form1_tribunal_details": body.tribunal_details,
        "form1_licence_revoked_declaration": body.licence_revoked_declaration,
        "form1_licence_revoked_details": body.licence_revoked_details,
        "form1_kyc_status": "submitted",
        "form1_submitted_at": _now(),
        "updated_at": _now(),
    }

    # Automated identity check: name + DOB present → verified
    can_auto_verify = bool(body.full_legal_name and body.date_of_birth)
    if can_auto_verify:
        form_data["form1_kyc_status"] = "verified"
        form_data["form1_verified_at"] = _now()
    else:
        _queue_human_review(
            subject_type="landlord",
            subject_id=user_id,
            review_type="form1_kyc_identity_check",
            tier=1,
            metadata={"profile_id": profile_id},
        )

    try:
        result = (
            _sb.table("landlord_profiles")
            .update(form_data)
            .eq("id", profile_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    return {
        "form": "form1_kyc",
        "status": form_data["form1_kyc_status"],
        "auto_verified": can_auto_verify,
        "profile": result.data[0] if result.data else {},
    }


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/form2  — Authority to List
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/form2")
async def submit_form2_authority(user_id: str, body: Form2Authority, current: CurrentUserId):
    """
    Submit Authority to List.
    CRITICAL RULE: No listing is published on the basis of an agent's authority alone.
    The registered owner is always contacted. owner_contact_confirmed is set to False;
    a human_review task is queued to confirm owner contact regardless of authority_type.
    Crown/Council verification is mocked with a 1-second async delay.
    """
    assert_same_user(user_id, current)
    profile = _get_profile(user_id)
    _require_prior_form(profile, "form1_kyc_status", 2)
    profile_id = profile["id"]

    valid_authority_types = {"owner", "agent_with_authority", "property_manager"}
    if body.authority_type not in valid_authority_types:
        raise HTTPException(
            status_code=422,
            detail=f"authority_type must be one of: {sorted(valid_authority_types)}",
        )

    form_data = {
        "form2_authority_type": body.authority_type,
        "form2_title_deed_storage_path": body.title_deed_storage_path,
        "form2_registered_owner_name": body.registered_owner_name,
        "form2_authority_letter_storage_path": body.authority_letter_storage_path,
        "form2_owner_contact_phone": body.owner_contact_phone,
        "form2_owner_contact_email": body.owner_contact_email,
        "form2_authority_status": "submitted",
        "form2_submitted_at": _now(),
        "crown_verification_status": "pending",
        # CRITICAL: owner contact is never assumed — always requires confirmation
        "owner_contact_confirmed": False,
        "updated_at": _now(),
    }

    try:
        result = (
            _sb.table("landlord_profiles")
            .update(form_data)
            .eq("id", profile_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    # Queue human review to confirm owner contact — mandatory regardless of authority type
    _queue_human_review(
        subject_type="landlord",
        subject_id=user_id,
        review_type="form2_owner_contact_confirmation",
        tier=1,
        metadata={
            "registered_owner_name": body.registered_owner_name,
            "owner_contact_phone": body.owner_contact_phone,
            "owner_contact_email": body.owner_contact_email,
            "authority_type": body.authority_type,
            "profile_id": profile_id,
            "rule": "No listing is published on the basis of an agent's authority alone. The registered owner is always contacted.",
        },
    )

    # Mock Crown/Council verification — 1-second async delay, then set verified
    async def _mock_crown_verify() -> None:
        await asyncio.sleep(1)
        try:
            # In production, this would call a real Crown/Council API.
            # Discrepancies would queue a human_review instead of auto-verifying.
            _sb.table("landlord_profiles").update(
                {
                    "crown_verification_status": "verified",
                    "form2_authority_status": "verified",
                    "updated_at": _now(),
                }
            ).eq("id", profile_id).execute()
        except Exception:
            _queue_human_review(
                subject_type="landlord",
                subject_id=user_id,
                review_type="form2_crown_verification_discrepancy",
                tier=1,
                metadata={"profile_id": profile_id},
            )

    asyncio.create_task(_mock_crown_verify())

    return {
        "form": "form2_authority",
        "status": "submitted",
        "crown_verification_status": "pending",
        "owner_contact_confirmed": False,
        "note": (
            "Owner contact confirmation has been queued for human review. "
            "Crown/Council verification is in progress. "
            "No listing will be published until the registered owner is contacted."
        ),
        "profile": result.data[0] if result.data else {},
    }


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/form3  — Municipal Records Declaration
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/form3")
async def submit_form3_municipal(user_id: str, body: Form3Municipal, current: CurrentUserId):
    """
    Submit Municipal Records Declaration.
    Automated where a city API is available; otherwise queued for human review.
    (Mock: auto-verify immediately for all submissions.)
    """
    assert_same_user(user_id, current)
    profile = _get_profile(user_id)
    _require_prior_form(profile, "form2_authority_status", 3)
    profile_id = profile["id"]

    form_data = {
        "form3_building_permit_status": body.building_permit_status,
        "form3_is_legal_dwelling": body.is_legal_dwelling,
        "form3_legal_dwelling_confirmation": body.legal_dwelling_confirmation,
        "form3_outstanding_orders": body.outstanding_orders,
        "form3_outstanding_orders_detail": body.outstanding_orders_detail,
        "form3_zoning_classification": body.zoning_classification,
        "form3_is_residential_zoned": body.is_residential_zoned,
        "form3_is_secondary_suite": body.is_secondary_suite,
        "form3_is_legal_secondary_suite": body.is_legal_secondary_suite,
        "form3_municipal_status": "submitted",
        "form3_submitted_at": _now(),
        "updated_at": _now(),
    }

    # Mock: city API assumed available — auto-verify
    # In production, check city API; fall back to human_review if unavailable.
    city_api_available = True  # Replace with real city API check in production
    if city_api_available:
        form_data["form3_municipal_status"] = "verified"
        form_data["form3_verified_at"] = _now()
    else:
        _queue_human_review(
            subject_type="landlord",
            subject_id=user_id,
            review_type="form3_municipal_records",
            tier=1,
            metadata={"profile_id": profile_id},
        )

    try:
        result = (
            _sb.table("landlord_profiles")
            .update(form_data)
            .eq("id", profile_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    return {
        "form": "form3_municipal",
        "status": form_data["form3_municipal_status"],
        "profile": result.data[0] if result.data else {},
    }


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/form4  — Property History Disclosure
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/form4")
async def submit_form4_history(user_id: str, body: Form4History, current: CurrentUserId):
    """Submit Property History Disclosure. Stored and marked 'submitted'."""
    assert_same_user(user_id, current)
    profile = _get_profile(user_id)
    _require_prior_form(profile, "form3_municipal_status", 4)
    profile_id = profile["id"]

    form_data = {
        "form4_last_inspection_date": body.last_inspection_date,
        "form4_inspector_name": body.inspector_name,
        "form4_inspector_licence": body.inspector_licence,
        "form4_known_deficiencies": body.known_deficiencies,
        "form4_active_construction_building": body.active_construction_building,
        "form4_active_construction_adjacent": body.active_construction_adjacent,
        "form4_construction_detail": body.construction_detail,
        "form4_water_damage_36mo": body.water_damage_36mo,
        "form4_water_damage_detail": body.water_damage_detail,
        "form4_mould_48mo": body.mould_48mo,
        "form4_mould_detail": body.mould_detail,
        "form4_mould_clearance_confirmed": body.mould_clearance_confirmed,
        "form4_pest_24mo": body.pest_24mo,
        "form4_pest_detail": body.pest_detail,
        "form4_insurance_claims_36mo": body.insurance_claims_36mo,
        "form4_insurance_claims_detail": body.insurance_claims_detail,
        "form4_utility_providers": body.utility_providers,
        "form4_utility_consumption_averages": body.utility_consumption_averages,
        "form4_history_status": "submitted",
        "form4_submitted_at": _now(),
        "updated_at": _now(),
    }

    # Form 4 is disclosure only — mark verified on submission
    form_data["form4_history_status"] = "verified"
    form_data["form4_verified_at"] = _now()

    try:
        result = (
            _sb.table("landlord_profiles")
            .update(form_data)
            .eq("id", profile_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    return {
        "form": "form4_property_history",
        "status": "verified",
        "profile": result.data[0] if result.data else {},
    }


# ---------------------------------------------------------------------------
# POST /profile/{user_id}/form5  — Platform Agreement
# ---------------------------------------------------------------------------


@router.post("/profile/{user_id}/form5")
async def submit_form5_agreement(user_id: str, body: Form5Agreement, current: CurrentUserId):
    """
    Submit Platform Agreement.
    All agreed_* booleans must be TRUE or 422 is returned.
    If all 5 forms are verified after this submission, verification_status
    is set to 'verified'.
    """
    assert_same_user(user_id, current)
    profile = _get_profile(user_id)
    _require_prior_form(profile, "form4_history_status", 5)
    profile_id = profile["id"]

    agreement_fields = {
        "agreed_terms_of_service": body.agreed_terms_of_service,
        "agreed_fair_housing": body.agreed_fair_housing,
        "agreed_no_discriminatory_screening": body.agreed_no_discriminatory_screening,
        "agreed_owner_contact_obligation": body.agreed_owner_contact_obligation,
        "agreed_deposit_protection": body.agreed_deposit_protection,
    }

    failing = [field for field, value in agreement_fields.items() if not value]
    if failing:
        raise HTTPException(
            status_code=422,
            detail=(
                f"All platform agreement declarations must be accepted. "
                f"The following were not accepted: {failing}"
            ),
        )

    form_data = {
        **{f"form5_{k}": v for k, v in agreement_fields.items()},
        "form5_deposit_protection_scheme_name": body.deposit_protection_scheme_name,
        "form5_deposit_protection_scheme_ref": body.deposit_protection_scheme_ref,
        "form5_signatory_name": body.signatory_name,
        "form5_agreement_status": "verified",
        "form5_submitted_at": _now(),
        "form5_verified_at": _now(),
        "updated_at": _now(),
    }

    # Check whether all 5 forms are now verified
    all_forms_verified = all([
        profile.get("form1_kyc_status") == "verified",
        profile.get("form2_authority_status") == "verified",
        profile.get("form3_municipal_status") == "verified",
        profile.get("form4_history_status") == "verified",
        # form5 is being verified now
    ])

    if all_forms_verified:
        form_data["verification_status"] = "verified"
        form_data["verified_at"] = _now()

    try:
        result = (
            _sb.table("landlord_profiles")
            .update(form_data)
            .eq("id", profile_id)
            .execute()
        )
    except Exception as exc:
        raise _db_error(exc)

    return {
        "form": "form5_platform_agreement",
        "status": "verified",
        "verification_status": form_data.get("verification_status", "pending"),
        "all_forms_complete": all_forms_verified,
        "profile": result.data[0] if result.data else {},
    }


# ---------------------------------------------------------------------------
# GET /profile/{user_id}/status
# ---------------------------------------------------------------------------


@router.get("/profile/{user_id}/status")
async def get_verification_status(user_id: str, current: CurrentUserId):
    """
    Return which forms are complete/pending, the overall verification status,
    and what is blocking publication.
    """
    assert_same_user(user_id, current)
    profile = _get_profile(user_id)

    forms = {
        "form1_kyc": profile.get("form1_kyc_status", "pending"),
        "form2_authority": profile.get("form2_authority_status", "pending"),
        "form3_municipal": profile.get("form3_municipal_status", "pending"),
        "form4_history": profile.get("form4_history_status", "pending"),
        "form5_agreement": profile.get("form5_agreement_status", "pending"),
    }

    blocking = [label for label, status in forms.items() if status != "verified"]

    owner_contact_blocking = not profile.get("owner_contact_confirmed", False)
    if owner_contact_blocking:
        blocking.append("owner_contact_confirmation")

    return {
        "user_id": user_id,
        "verification_status": profile.get("verification_status", "pending"),
        "crown_verification_status": profile.get("crown_verification_status", "pending"),
        "owner_contact_confirmed": profile.get("owner_contact_confirmed", False),
        "forms": forms,
        "blocking_publication": blocking,
        "can_publish": len(blocking) == 0 and profile.get("verification_status") == "verified",
    }

-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
-- FlatFinder™ — Migration 006: Verification System
-- FF-CORE-009 (Tenant) + FF-CORE-010 (Landlord) + Baseline PRD
-- Trademarks and Patents Pending (CIPO). Proprietary and Confidential.

-- ─────────────────────────────────────────────────────────────────────────────
-- TENANT PROFILES & VERIFICATION (FF-CORE-009)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenant_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE,  -- auth.users

    -- Verification state
    verification_status TEXT NOT NULL DEFAULT 'unverified'
                            CHECK (verification_status IN ('unverified','pending','verified','rejected')),
    documentation_tier  INT CHECK (documentation_tier BETWEEN 1 AND 6),
    verified_at         TIMESTAMPTZ,
    verified_by         TEXT,  -- 'automated' | 'human_review'
    rejection_reason    TEXT,

    -- Search preferences
    desired_cities      TEXT[],
    desired_property_types TEXT[],
    desired_move_in_from DATE,
    desired_move_in_to   DATE,
    max_rent_cents      INT,   -- stored in cents
    min_bedrooms        INT,

    -- Non-negotiable requirements (FF-CORE-011 Filter 5)
    non_negotiables     JSONB NOT NULL DEFAULT '[]',
    -- e.g. [{"key":"in_suite_laundry","label":"In-suite laundry"},{"key":"pets_cats","label":"Cats permitted"}]

    -- Priority status (granted when unfairly cancelled from a match)
    has_priority        BOOLEAN NOT NULL DEFAULT FALSE,
    priority_granted_at TIMESTAMPTZ,
    priority_reason     TEXT,

    -- Non-response flag count (against landlords — tracked per tenant for recovery)
    non_response_flags_received INT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenant_profiles(id) ON DELETE CASCADE,
    tier            INT NOT NULL CHECK (tier BETWEEN 1 AND 6),
    doc_type        TEXT NOT NULL,
    -- e.g. 'bank_statement_3mo', 'employment_contract', 'payslip', 'noa', 'accountant_letter',
    --      'pension_statement', 'investment_statement', 'alternative_documentation'

    -- Storage reference (Supabase Storage bucket)
    storage_path    TEXT NOT NULL,
    file_name       TEXT,
    mime_type       TEXT,

    -- Verification
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at     TIMESTAMPTZ,
    verified_by     TEXT,
    rejection_reason TEXT,

    -- Tier 1 specific: reserve ratio check
    reserve_ratio   FLOAT,  -- actual ratio found in statements (must be >= 6.0)

    -- Tier 2 specific: net income extracted
    net_monthly_income_cents INT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- LANDLORD PROFILES & VERIFICATION (FF-CORE-010)
-- 5 sequential forms — none skippable
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS landlord_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE,  -- auth.users

    -- Verification state across all 5 forms
    verification_status TEXT NOT NULL DEFAULT 'unverified'
                            CHECK (verification_status IN ('unverified','in_progress','verified','suspended','banned')),

    -- Which forms are complete
    form1_kyc_status        TEXT NOT NULL DEFAULT 'pending' CHECK (form1_kyc_status IN ('pending','submitted','verified','rejected')),
    form2_authority_status  TEXT NOT NULL DEFAULT 'pending' CHECK (form2_authority_status IN ('pending','submitted','verified','rejected')),
    form3_municipal_status  TEXT NOT NULL DEFAULT 'pending' CHECK (form3_municipal_status IN ('pending','submitted','verified','rejected')),
    form4_history_status    TEXT NOT NULL DEFAULT 'pending' CHECK (form4_history_status IN ('pending','submitted','verified','rejected')),
    form5_agreement_status  TEXT NOT NULL DEFAULT 'pending' CHECK (form5_agreement_status IN ('pending','submitted','verified','rejected')),

    -- Do Not Fly List check
    is_on_dnfl      BOOLEAN NOT NULL DEFAULT FALSE,
    dnfl_entry_id   UUID REFERENCES do_not_fly_list(id),

    -- Non-response flag count (FF-CORE-007 §5.2)
    non_response_flags  INT NOT NULL DEFAULT 0,
    -- 3 flags in 12 months = auto suspension
    last_flag_reset_at  TIMESTAMPTZ,

    -- Crown/Council verification
    crown_verification_status TEXT NOT NULL DEFAULT 'pending'
                                CHECK (crown_verification_status IN ('pending','verified','discrepancy','referred')),
    crown_verified_at   TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Form 1 — KYC
CREATE TABLE IF NOT EXISTS landlord_form1_kyc (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landlord_id     UUID NOT NULL UNIQUE REFERENCES landlord_profiles(id) ON DELETE CASCADE,

    full_legal_name TEXT NOT NULL,
    date_of_birth   DATE NOT NULL,
    -- Government ID stored as Supabase Storage reference (never raw)
    gov_id_storage_path TEXT NOT NULL,
    gov_id_type     TEXT NOT NULL CHECK (gov_id_type IN ('passport','drivers_licence','provincial_id','international_passport')),

    residential_address JSONB NOT NULL,
    -- {"street":"123 Main St","city":"Toronto","province":"ON","postal_code":"M5V 1A1"}
    address_proof_storage_path TEXT NOT NULL,

    primary_phone   TEXT NOT NULL,
    primary_email   TEXT NOT NULL,

    -- Declarations
    tribunal_decisions_declaration BOOLEAN NOT NULL,  -- TRUE = has had decisions against them
    tribunal_details TEXT,
    licence_revoked_declaration BOOLEAN NOT NULL,
    licence_revoked_details TEXT,

    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at     TIMESTAMPTZ,
    verified_by     TEXT
);

-- Form 2 — Authority to List
CREATE TABLE IF NOT EXISTS landlord_form2_authority (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landlord_id     UUID NOT NULL REFERENCES landlord_profiles(id) ON DELETE CASCADE,
    listing_id      UUID,  -- set when authority is tied to a specific listing

    authority_type  TEXT NOT NULL CHECK (authority_type IN ('owner','agent_with_authority','property_manager')),

    -- Ownership proof
    title_deed_storage_path TEXT NOT NULL,
    registered_owner_name TEXT NOT NULL,

    -- Agent/PM authority (where authority_type != 'owner')
    authority_letter_storage_path TEXT,
    owner_contact_phone TEXT,
    owner_contact_email TEXT,
    -- FlatFinder contacts owner directly — confirm this was done
    owner_contact_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    owner_contacted_at TIMESTAMPTZ,
    owner_confirmed_at TIMESTAMPTZ,

    -- Crown/Council cross-reference result
    registry_name   TEXT,       -- e.g. 'Teranet', 'HM Land Registry'
    registry_match  BOOLEAN,
    registry_checked_at TIMESTAMPTZ,
    discrepancy_detail TEXT,

    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at     TIMESTAMPTZ,
    verified_by     TEXT
);

-- Form 3 — Municipal Records Declaration
CREATE TABLE IF NOT EXISTS landlord_form3_municipal (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landlord_id     UUID NOT NULL REFERENCES landlord_profiles(id) ON DELETE CASCADE,
    listing_id      UUID,

    building_permit_status TEXT NOT NULL,
    is_legal_dwelling BOOLEAN NOT NULL,
    legal_dwelling_confirmation TEXT,  -- registration number / reference
    outstanding_orders BOOLEAN NOT NULL,
    outstanding_orders_detail TEXT,
    zoning_classification TEXT NOT NULL,
    is_residential_zoned BOOLEAN NOT NULL,

    -- Secondary suite / basement specific
    is_secondary_suite BOOLEAN NOT NULL DEFAULT FALSE,
    is_legal_secondary_suite BOOLEAN,

    -- Automated cross-reference result
    city_db_crossref_status TEXT DEFAULT 'pending'
                                CHECK (city_db_crossref_status IN ('pending','verified','discrepancy','manual_review')),
    city_db_crossref_at TIMESTAMPTZ,

    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at     TIMESTAMPTZ,
    verified_by     TEXT
);

-- Form 4 — Property History Disclosure (Baseline PRD §6 + FF-CORE-010)
CREATE TABLE IF NOT EXISTS landlord_form4_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landlord_id     UUID NOT NULL REFERENCES landlord_profiles(id) ON DELETE CASCADE,
    listing_id      UUID,

    -- Inspection
    last_inspection_date DATE NOT NULL,
    inspector_name  TEXT NOT NULL,
    inspector_licence TEXT NOT NULL,

    -- Known deficiencies (mandatory — 'None known' if none)
    known_deficiencies TEXT NOT NULL,

    -- Active construction
    active_construction_building BOOLEAN NOT NULL DEFAULT FALSE,
    active_construction_adjacent BOOLEAN NOT NULL DEFAULT FALSE,
    construction_detail TEXT,

    -- Water history (36 months)
    water_damage_36mo BOOLEAN NOT NULL DEFAULT FALSE,
    water_damage_detail TEXT,

    -- Mould (48 months)
    mould_48mo      BOOLEAN NOT NULL DEFAULT FALSE,
    mould_detail    TEXT,
    mould_clearance_confirmed BOOLEAN,

    -- Pest (24 months)
    pest_24mo       BOOLEAN NOT NULL DEFAULT FALSE,
    pest_detail     TEXT,

    -- Insurance claims (36 months)
    insurance_claims_36mo BOOLEAN NOT NULL DEFAULT FALSE,
    insurance_claims_detail TEXT,

    -- Utilities
    utility_providers JSONB,
    -- {"electricity":"Toronto Hydro","gas":"Enbridge","water":"City of Toronto","internet":"Rogers"}
    utility_consumption_averages JSONB,
    -- {"electricity_kwh_avg":450,"gas_m3_avg":30}

    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at     TIMESTAMPTZ,
    verified_by     TEXT
);

-- Form 5 — Platform Agreement
CREATE TABLE IF NOT EXISTS landlord_form5_agreement (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    landlord_id     UUID NOT NULL UNIQUE REFERENCES landlord_profiles(id) ON DELETE CASCADE,

    -- All agreements are boolean — TRUE = agreed
    agreed_listing_standards        BOOLEAN NOT NULL CHECK (agreed_listing_standards = TRUE),
    agreed_vmc_24h_window           BOOLEAN NOT NULL CHECK (agreed_vmc_24h_window = TRUE),
    agreed_deposit_protection       BOOLEAN NOT NULL CHECK (agreed_deposit_protection = TRUE),
    deposit_protection_scheme_name  TEXT,
    deposit_protection_scheme_ref   TEXT,
    agreed_no_prefee_instruments    BOOLEAN NOT NULL CHECK (agreed_no_prefee_instruments = TRUE),
    agreed_verification_access      BOOLEAN NOT NULL CHECK (agreed_verification_access = TRUE),
    agreed_accuracy_responsibility  BOOLEAN NOT NULL CHECK (agreed_accuracy_responsibility = TRUE),
    agreed_breach_consequences      BOOLEAN NOT NULL CHECK (agreed_breach_consequences = TRUE),

    -- Declaration
    signatory_name  TEXT NOT NULL,
    signed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address      INET,           -- audit trail
    user_agent      TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- LISTING SCHEMA (Baseline PRD — full property data)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listing_details (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id          UUID NOT NULL UNIQUE,  -- FK to listings table

    -- Section 1: Classification
    legal_ownership_structure TEXT NOT NULL,
    -- condominium_unit | rental_apartment | freehold_house | semi_detached |
    -- townhouse | basement_apartment | garden_suite | rooming_house | other
    what_is_rented  TEXT NOT NULL CHECK (what_is_rented IN ('entire_property','portion_no_landlord','portion_landlord_present','shared_unit')),
    rental_licence_number TEXT,
    is_legal_secondary_suite BOOLEAN,
    active_permits  BOOLEAN NOT NULL DEFAULT FALSE,
    active_permits_detail TEXT,

    -- Section 2: Physical Identity
    address_legal   JSONB NOT NULL,
    sqft            INT,
    pct_below_grade INT NOT NULL DEFAULT 0 CHECK (pct_below_grade BETWEEN 0 AND 100),
    storeys_in_unit INT NOT NULL DEFAULT 1,
    floor_number    INT,
    total_floors_building INT,
    year_built      INT,
    year_last_renovated INT,

    -- Section 2.3: Layout
    bedrooms        INT NOT NULL,
    dens            INT NOT NULL DEFAULT 0,
    bathrooms_full  INT NOT NULL DEFAULT 0,
    bathrooms_half  INT NOT NULL DEFAULT 0,
    has_living_room BOOLEAN NOT NULL DEFAULT TRUE,
    dining_area     TEXT CHECK (dining_area IN ('separate','open_to_living','none')),
    kitchen_type    TEXT CHECK (kitchen_type IN ('separate','open_concept')),

    -- Section 3: Systems & Appliances
    heating_type    TEXT,
    heating_fuel    TEXT,
    heating_control TEXT CHECK (heating_control IN ('tenant','building','landlord')),
    has_central_ac  BOOLEAN NOT NULL DEFAULT FALSE,
    window_ac       TEXT CHECK (window_ac IN ('provided','tenant_may_install','not_permitted','na')),
    kitchen_appliances JSONB,
    laundry_insuite_washer BOOLEAN NOT NULL DEFAULT FALSE,
    laundry_insuite_dryer  BOOLEAN NOT NULL DEFAULT FALSE,
    laundry_location TEXT,  -- if not in-suite
    laundry_cost    TEXT,
    hot_water_type  TEXT,

    -- Section 4: Inclusions
    inclusions      JSONB NOT NULL DEFAULT '{}',
    -- {"heat":"included","electricity":"tenant_pays","water":"included","internet":"not_available","parking":"included"}
    parking_type    TEXT,
    parking_included BOOLEAN,
    parking_extra_cost_cents INT,
    ev_charging     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Section 5: Building & Access
    has_elevator    BOOLEAN NOT NULL DEFAULT FALSE,
    accessible_unit BOOLEAN NOT NULL DEFAULT FALSE,
    accessible_building BOOLEAN NOT NULL DEFAULT FALSE,
    key_fob         BOOLEAN NOT NULL DEFAULT FALSE,
    concierge       TEXT CHECK (concierge IN ('24_hour','part_time','none')),
    intercom        BOOLEAN NOT NULL DEFAULT FALSE,
    building_amenities JSONB NOT NULL DEFAULT '{}',
    pets_permitted  TEXT CHECK (pets_permitted IN ('yes','no','case_by_case')),
    pet_restrictions TEXT,
    smoking_in_unit BOOLEAN NOT NULL DEFAULT FALSE,
    smoking_on_balcony BOOLEAN,

    -- Section 6: Disclosure
    known_deficiencies TEXT NOT NULL DEFAULT 'None known.',
    construction_building BOOLEAN NOT NULL DEFAULT FALSE,
    construction_adjacent BOOLEAN NOT NULL DEFAULT FALSE,
    construction_detail TEXT,
    water_damage_5yr BOOLEAN NOT NULL DEFAULT FALSE,
    mould_5yr       BOOLEAN NOT NULL DEFAULT FALSE,
    outstanding_work_orders BOOLEAN NOT NULL DEFAULT FALSE,

    -- Section 7: Landlord Declaration
    declaration_submitted_by TEXT NOT NULL,
    declaration_capacity TEXT NOT NULL CHECK (declaration_capacity IN ('owner','authorized_agent','property_manager')),
    declaration_date DATE NOT NULL,

    -- Floor plan (mandatory)
    floor_plan_storage_path TEXT,
    floor_plan_uploaded_at TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tenant_profiles_user   ON tenant_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_tenant_profiles_status ON tenant_profiles(verification_status);
CREATE INDEX IF NOT EXISTS idx_landlord_profiles_user ON landlord_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_landlord_profiles_status ON landlord_profiles(verification_status);
CREATE INDEX IF NOT EXISTS idx_listing_details_listing ON listing_details(listing_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS POLICIES
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE tenant_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_form1_kyc ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_form2_authority ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_form3_municipal ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_form4_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE landlord_form5_agreement ENABLE ROW LEVEL SECURITY;
ALTER TABLE listing_details ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_own_profile"    ON tenant_profiles    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "tenant_own_documents"  ON tenant_documents   FOR ALL USING (
    EXISTS (SELECT 1 FROM tenant_profiles tp WHERE tp.id = tenant_documents.tenant_id AND tp.user_id = auth.uid())
);
CREATE POLICY "landlord_own_profile"  ON landlord_profiles  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "landlord_own_form1"    ON landlord_form1_kyc FOR ALL USING (
    EXISTS (SELECT 1 FROM landlord_profiles lp WHERE lp.id = landlord_form1_kyc.landlord_id AND lp.user_id = auth.uid())
);
CREATE POLICY "landlord_own_form5"    ON landlord_form5_agreement FOR ALL USING (
    EXISTS (SELECT 1 FROM landlord_profiles lp WHERE lp.id = landlord_form5_agreement.landlord_id AND lp.user_id = auth.uid())
);
CREATE POLICY "listing_details_public_read" ON listing_details FOR SELECT USING (TRUE);

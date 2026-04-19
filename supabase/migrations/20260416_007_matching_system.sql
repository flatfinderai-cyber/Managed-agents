-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
-- FlatFinder™ — Migration 007: Matching System (FF-CORE-011)
-- Anti-Gatekeeping Affordability Algorithm™
-- Trademarks and Patents Pending (CIPO). Proprietary and Confidential.

-- ─────────────────────────────────────────────────────────────────────────────
-- MATCHES
-- Produced by the Anti-Gatekeeping Affordability Algorithm™.
-- The ranking methodology is proprietary. Only the output is stored here.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,   -- auth.users
    listing_id      UUID NOT NULL,
    landlord_id     UUID NOT NULL,   -- auth.users

    -- Status: pending → confirmed_both → vmc_open → vmc_complete → tenancy | cancelled
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending',
                            'confirmed_tenant',
                            'confirmed_landlord',
                            'confirmed_both',
                            'vmc_open',
                            'vmc_complete',
                            'tenancy',
                            'cancelled_tenant',
                            'cancelled_landlord',
                            'cancelled_platform',
                            'cancelled_nonresponse'
                        )),

    -- Filter pass record (human-readable outputs only — FF-CORE-008 §4)
    filter1_listing_verified    BOOLEAN,
    filter2_tenant_verified     BOOLEAN,
    filter3_location_match      BOOLEAN,
    filter4_availability_match  BOOLEAN,
    filter5_non_negotiables_met BOOLEAN,
    filter6_no_flags            BOOLEAN,
    all_filters_passed          BOOLEAN GENERATED ALWAYS AS (
        filter1_listing_verified AND
        filter2_tenant_verified AND
        filter3_location_match AND
        filter4_availability_match AND
        filter5_non_negotiables_met AND
        filter6_no_flags
    ) STORED,

    -- Affordability (40% of net income — NEVER 3x gross)
    -- Values stored but NOT exposed to landlord
    tenant_net_monthly_cents    INT,
    rent_cents                  INT,
    affordability_pct           FLOAT,   -- rent / net_monthly * 100
    is_affordable               BOOLEAN, -- pct <= 40

    -- Rank position in the tenant's match list (opaque — not shown to landlord)
    rank_position               INT,

    confirmed_tenant_at         TIMESTAMPTZ,
    confirmed_landlord_at       TIMESTAMPTZ,
    vmc_thread_id               UUID REFERENCES vmc_threads(id),

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DISCRIMINATION FLAGS (FF-CORE-008-S7)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS discrimination_flags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID,
    landlord_id     UUID,
    reported_by     UUID,           -- user who reported (NULL if automated)
    source          TEXT NOT NULL CHECK (source IN ('automated_scan','user_report','human_review')),

    -- Classification
    flag_type       TEXT NOT NULL CHECK (flag_type IN ('discriminatory','predatory','both')),
    grounds         TEXT[],
    -- e.g. ['age','family_status'] for discriminatory; ['ghost_listing','deposit_before_vmc'] for predatory
    confidence_score FLOAT,        -- 0.0–1.0 from automated detection
    flagged_content TEXT,          -- the specific text / pattern that triggered the flag
    -- NOTE: flagged_content is NOT shown to the landlord to prevent evasion

    -- Action taken
    action          TEXT NOT NULL DEFAULT 'pending_review'
                        CHECK (action IN (
                            'pending_review',
                            'referred_human_review',
                            'listing_suspended',
                            'listing_removed',
                            'account_suspended',
                            'account_banned',
                            'law_enforcement_referred',
                            'cleared'
                        )),
    action_taken_at TIMESTAMPTZ,

    -- Appeal (discriminatory only — one appeal, 14 days)
    appeal_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    appeal_submitted_at TIMESTAMPTZ,
    appeal_deadline TIMESTAMPTZ,   -- 14 days from ban notification
    appeal_outcome  TEXT CHECK (appeal_outcome IN ('upheld','denied')),
    appeal_reviewed_by TEXT,       -- must be different reviewer

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_matches_tenant   ON matches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_matches_listing  ON matches(listing_id);
CREATE INDEX IF NOT EXISTS idx_matches_landlord ON matches(landlord_id);
CREATE INDEX IF NOT EXISTS idx_matches_status   ON matches(status);
CREATE INDEX IF NOT EXISTS idx_disc_flags_listing   ON discrimination_flags(listing_id);
CREATE INDEX IF NOT EXISTS idx_disc_flags_landlord  ON discrimination_flags(landlord_id);
CREATE INDEX IF NOT EXISTS idx_disc_flags_action    ON discrimination_flags(action);

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE discrimination_flags ENABLE ROW LEVEL SECURITY;

-- A tenant can only see their own matches
CREATE POLICY "matches_tenant_read" ON matches
    FOR SELECT USING (auth.uid() = tenant_id);

-- A landlord can only see matches on their listings (but NOT rank, score, tier)
CREATE POLICY "matches_landlord_read" ON matches
    FOR SELECT USING (auth.uid() = landlord_id);

-- Discrimination flags: no public read
CREATE POLICY "disc_flags_no_public" ON discrimination_flags
    FOR SELECT USING (FALSE);

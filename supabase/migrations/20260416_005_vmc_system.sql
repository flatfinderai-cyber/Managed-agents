-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
-- FlatFinder™ — Migration 005: VMC System (FF-CORE-007) + Human Review (FF-CORE-008)
-- Trademarks and Patents Pending (CIPO). Proprietary and Confidential.

-- ─────────────────────────────────────────────────────────────────────────────
-- VMC THREADS
-- A thread opens the moment both parties confirm a match.
-- It is a hard gate — no bypass for any tier.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vmc_threads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id            UUID NOT NULL,                  -- FK to matches table
    listing_id          UUID NOT NULL,
    landlord_id         UUID NOT NULL,                  -- auth.users
    tenant_id           UUID NOT NULL,                  -- auth.users

    -- State machine: pending → open → complete | cancelled_nonresponse | cancelled_withdrawal | cancelled_platform
    status              TEXT NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open','complete','cancelled_nonresponse','cancelled_withdrawal','cancelled_platform')),

    -- Completion tracking (each party needs 3 valid messages)
    landlord_valid_count INT NOT NULL DEFAULT 0,
    tenant_valid_count   INT NOT NULL DEFAULT 0,

    -- 24-hour landlord response window
    -- Clock starts from first valid tenant message
    window_start_at      TIMESTAMPTZ,
    reminder_12h_sent    BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_20h_sent    BOOLEAN NOT NULL DEFAULT FALSE,
    window_expires_at    TIMESTAMPTZ,

    -- Completion / cancellation timestamps
    completed_at         TIMESTAMPTZ,
    cancelled_at         TIMESTAMPTZ,
    cancellation_reason  TEXT,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- VMC MESSAGES
-- Every message is logged, timestamped, and validated server-side.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vmc_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       UUID NOT NULL REFERENCES vmc_threads(id) ON DELETE CASCADE,
    sender_role     TEXT NOT NULL CHECK (sender_role IN ('landlord', 'tenant')),
    sender_id       UUID NOT NULL,

    -- Message content — encrypted at rest in prod via Supabase Vault
    content         TEXT NOT NULL,
    word_count      INT,

    -- Validation results (FF-CORE-007 §4)
    is_valid        BOOLEAN NOT NULL DEFAULT FALSE,  -- passes ALL checks
    check_length    BOOLEAN,   -- §4.2 — 40 word minimum
    check_dict      BOOLEAN,   -- §4.3 — 85% dictionary integrity
    check_semantic  BOOLEAN,   -- §4.4 — coherence score >= 0.60
    check_unique    BOOLEAN,   -- §4.5 — < 60% similarity to prior messages
    check_template  BOOLEAN,   -- §4.6 — not predominantly filler
    check_responsive BOOLEAN,  -- §4.7 — response pairing (min 90s gap)

    semantic_score  FLOAT,     -- 0.0–1.0 coherence score
    dict_pct        FLOAT,     -- % of words resolving to dictionary entries
    similarity_max  FLOAT,     -- max cosine similarity to prior messages

    rejection_reason TEXT,     -- plain-language explanation if invalid

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DO NOT FLY LIST (FF-CORE-008-S7 §5)
-- Permanent. No expiry. No removal process.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS do_not_fly_list (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Identity fingerprint fields
    full_name       TEXT,
    date_of_birth   DATE,
    government_id_hash TEXT,       -- hashed, never store plaintext
    device_fingerprints TEXT[],
    ip_patterns     TEXT[],
    email_addresses TEXT[],
    payment_method_hashes TEXT[],

    -- Classification
    ban_reason      TEXT NOT NULL,  -- 'discriminatory_listing' | 'predatory_listing' | 'fraud' | 'harassment'
    ban_detail      TEXT,
    original_user_id UUID,          -- the banned account

    -- Legal referral
    law_enforcement_referred BOOLEAN NOT NULL DEFAULT FALSE,
    referral_date   TIMESTAMPTZ,
    referral_authority TEXT,        -- 'RCMP' | 'Metropolitan Police' | etc.

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- No updated_at — this record is immutable
);

-- ─────────────────────────────────────────────────────────────────────────────
-- HUMAN REVIEW QUEUE (FF-CORE-008)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS human_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type    TEXT NOT NULL CHECK (subject_type IN ('listing','landlord_profile','tenant_profile','vmc_thread')),
    subject_id      UUID NOT NULL,
    trigger_code    TEXT NOT NULL,  -- e.g. 'discrimination_flag_below_threshold', 'photo_mismatch', etc.
    trigger_detail  TEXT,

    -- Tier: 1=low/48h, 2=moderate/5 days, 3=high/10 days
    tier            INT NOT NULL DEFAULT 1 CHECK (tier IN (1,2,3)),

    -- Cost model (FF-CORE-008 §5)
    cost_model      TEXT NOT NULL DEFAULT 'no_cost'
                        CHECK (cost_model IN ('no_cost','cost_recovery','suspension')),

    -- Assignment
    reviewer_id     UUID,           -- internal reviewer
    assigned_at     TIMESTAMPTZ,
    due_at          TIMESTAMPTZ,

    -- Outcome
    status          TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','in_progress','cleared','found_against','referred_authority','suspended')),
    outcome_detail  TEXT,
    closed_at       TIMESTAMPTZ,

    -- Platform credit if cleared (one month subscription fee)
    credit_issued   BOOLEAN NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_vmc_threads_match     ON vmc_threads(match_id);
CREATE INDEX IF NOT EXISTS idx_vmc_threads_landlord  ON vmc_threads(landlord_id);
CREATE INDEX IF NOT EXISTS idx_vmc_threads_tenant    ON vmc_threads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vmc_threads_status    ON vmc_threads(status);
CREATE INDEX IF NOT EXISTS idx_vmc_messages_thread   ON vmc_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_vmc_messages_sender   ON vmc_messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_human_reviews_subject ON human_reviews(subject_id, subject_type);
CREATE INDEX IF NOT EXISTS idx_human_reviews_status  ON human_reviews(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS POLICIES
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE vmc_threads  ENABLE ROW LEVEL SECURITY;
ALTER TABLE vmc_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE do_not_fly_list ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_reviews ENABLE ROW LEVEL SECURITY;

-- VMC thread: only the landlord or tenant party can read their own thread
CREATE POLICY "vmc_thread_parties_read" ON vmc_threads
    FOR SELECT USING (auth.uid() = landlord_id OR auth.uid() = tenant_id);

-- VMC messages: only thread parties can read
CREATE POLICY "vmc_message_parties_read" ON vmc_messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM vmc_threads t
            WHERE t.id = vmc_messages.thread_id
              AND (t.landlord_id = auth.uid() OR t.tenant_id = auth.uid())
        )
    );

-- Do Not Fly List: no public read — service role only
CREATE POLICY "dnfl_no_public_read" ON do_not_fly_list
    FOR SELECT USING (FALSE);

-- Human reviews: no public read — service role only
CREATE POLICY "reviews_no_public_read" ON human_reviews
    FOR SELECT USING (FALSE);

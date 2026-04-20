-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
-- FlatFinder™ — Migration 008: Listing Vertical Stack Decisioning (FF-SCAM-001)
-- Proprietary and Confidential.

-- Persist one latest stack decision per listing for fast reads.
CREATE TABLE IF NOT EXISTS listing_stack_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id          UUID NOT NULL UNIQUE REFERENCES listings(id) ON DELETE CASCADE,

    decision            TEXT NOT NULL CHECK (decision IN ('pass','quarantine','block')),
    decision_reason     TEXT,
    layer_results       JSONB NOT NULL DEFAULT '{}',
    listing_fingerprint TEXT NOT NULL,
    confidence_summary  TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Immutable append-only audit trail for each decision run.
CREATE TABLE IF NOT EXISTS listing_stack_decision_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id          UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,

    decision            TEXT NOT NULL CHECK (decision IN ('pass','quarantine','block')),
    decision_reason     TEXT,
    layer_results       JSONB NOT NULL DEFAULT '{}',
    listing_fingerprint TEXT NOT NULL,
    confidence_summary  TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listing_stack_decisions_decision
    ON listing_stack_decisions(decision);
CREATE INDEX IF NOT EXISTS idx_listing_stack_decisions_fingerprint
    ON listing_stack_decisions(listing_fingerprint);
CREATE INDEX IF NOT EXISTS idx_listing_stack_events_listing_id
    ON listing_stack_decision_events(listing_id);
CREATE INDEX IF NOT EXISTS idx_listing_stack_events_created_at
    ON listing_stack_decision_events(created_at DESC);

-- Reuse the project-wide updated_at trigger function.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'listing_stack_decisions_updated_at'
        ) THEN
            CREATE TRIGGER listing_stack_decisions_updated_at
                BEFORE UPDATE ON listing_stack_decisions
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        END IF;
    END IF;
END $$;

ALTER TABLE listing_stack_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE listing_stack_decision_events ENABLE ROW LEVEL SECURITY;

-- Service role only. Never exposed directly to users.
CREATE POLICY "listing_stack_decisions_no_public" ON listing_stack_decisions
    FOR SELECT USING (FALSE);
CREATE POLICY "listing_stack_decision_events_no_public" ON listing_stack_decision_events
    FOR SELECT USING (FALSE);

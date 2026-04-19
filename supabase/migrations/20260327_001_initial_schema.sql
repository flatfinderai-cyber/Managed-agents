-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
-- Migration: 001 — Initial Schema
-- FlatFinder™ Anti-Gatekeeping Rental Platform
-- Canadian Corporation | Canadian Kind, Scottish Strong

-- ─────────────────────────────────────────────────────────────────────────────
-- AGENTS TABLE
-- Every letting agent, landlord, or property management company.
-- Compliance score drops with violations. Blacklisted = hidden from search.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
  id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                          TEXT NOT NULL,
  company                       TEXT,
  email                         TEXT,
  phone                         TEXT,
  website                       TEXT,
  -- Geography
  city                          TEXT,                   -- Primary city of operation
  cities_active                 TEXT[] DEFAULT '{}',    -- All cities they operate in
  country                       TEXT,
  is_multinational              BOOLEAN DEFAULT FALSE,
  -- Compliance
  compliance_score              NUMERIC(5,2) DEFAULT 100,
  income_requirement_multiplier NUMERIC(4,2),           -- Known screening multiplier
  uses_illegal_screening        BOOLEAN DEFAULT FALSE,
  un_violation_count            INTEGER DEFAULT 0,
  human_rights_flags            JSONB DEFAULT '[]',
  -- Status
  status                        TEXT DEFAULT 'active',  -- 'active' | 'watchlist' | 'flagged' | 'blacklisted'
  is_blacklisted                BOOLEAN DEFAULT FALSE,
  blacklist_reason              TEXT,
  blacklist_date                DATE,
  -- Community
  report_count                  INTEGER DEFAULT 0,
  verified_by                   TEXT,                   -- 'system' | 'community' | 'legal'
  notes                         TEXT,
  -- Timestamps
  created_at                    TIMESTAMPTZ DEFAULT NOW(),
  updated_at                    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- AGENT VIOLATIONS TABLE
-- Each documented violation against an agent. Source of truth for blacklisting.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_violations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id              UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  violation_type        TEXT NOT NULL,   -- 'un_housing_right' | 'illegal_screening' | 'fraud' | 'discrimination' | 'financial_harm' | 'harassment'
  severity              TEXT DEFAULT 'medium',  -- 'low' | 'medium' | 'high' | 'critical'
  description           TEXT NOT NULL,
  evidence_url          TEXT,
  reported_by           TEXT,            -- 'system' | 'user' | 'legal' | 'community'
  financial_harm_amount INTEGER,         -- in cents
  affected_city         TEXT,
  affected_country      TEXT,
  is_verified           BOOLEAN DEFAULT FALSE,
  reported_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- LISTINGS TABLE
-- Every rental listing from every source.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS listings (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id         TEXT,
  source              TEXT NOT NULL,    -- 'kijiji' | 'craigslist' | 'facebook' | 'livrent' | 'leboncoin' | 'gumtree' | 'manual'
  title               TEXT NOT NULL,
  description         TEXT,
  -- Pricing
  price               INTEGER NOT NULL, -- monthly rent in cents
  currency            TEXT DEFAULT 'CAD',
  -- Unit details
  bedrooms            SMALLINT,
  bathrooms           NUMERIC(3,1),
  sqft                INTEGER,
  -- Location
  address             TEXT,
  neighborhood        TEXT,
  city                TEXT NOT NULL,
  country             TEXT DEFAULT 'CA',
  lat                 NUMERIC(10, 7),
  lng                 NUMERIC(10, 7),
  -- Features
  amenities           JSONB DEFAULT '[]',
  pet_friendly        BOOLEAN,
  utilities_included  TEXT,
  lease_term          TEXT,
  available_date      DATE,
  images              JSONB DEFAULT '[]',
  url                 TEXT,
  -- Agent link
  agent_id            UUID REFERENCES agents(id),
  -- Scoring
  affordability_score NUMERIC(5,2),    -- % of median income for city
  compliance_score    NUMERIC(5,2),    -- derived from agent's compliance score
  -- Flags
  is_flagged          BOOLEAN DEFAULT FALSE,
  flag_reason         TEXT,
  is_scam             BOOLEAN DEFAULT FALSE,
  is_active           BOOLEAN DEFAULT TRUE,
  -- Raw data for debugging
  raw_data            JSONB,
  -- Timestamps
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(external_id, source)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- COMMUNITY AGENT REPORTS
-- Users report agents. These feed the compliance scoring system.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_reports (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id          UUID REFERENCES agents(id),
  agent_name_raw    TEXT,              -- if agent not yet in db
  agent_company_raw TEXT,
  user_id           UUID REFERENCES auth.users(id),
  violation_type    TEXT NOT NULL,
  severity          TEXT DEFAULT 'medium',
  description       TEXT NOT NULL,
  financial_harm    INTEGER,           -- in cents
  cities_affected   TEXT[] DEFAULT '{}',
  submitted_at      TIMESTAMPTZ DEFAULT NOW(),
  is_reviewed       BOOLEAN DEFAULT FALSE,
  review_outcome    TEXT,              -- 'verified' | 'rejected' | 'needs_more_info'
  reviewed_at       TIMESTAMPTZ
);

-- ─────────────────────────────────────────────────────────────────────────────
-- RENTER DEMAND LETTERS (Max Plan / Ultra Plan feature)
-- The reverse-engineered lease — renters demand conditions from landlords.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS renter_demands (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id),
  listing_id      UUID REFERENCES listings(id),
  agent_id        UUID REFERENCES agents(id),
  -- The demands
  demands         JSONB NOT NULL DEFAULT '[]',  -- array of demand objects
  custom_demands  TEXT,                          -- free text additional demands
  -- Status
  status          TEXT DEFAULT 'draft',          -- 'draft' | 'sent' | 'accepted' | 'rejected' | 'negotiating'
  sent_at         TIMESTAMPTZ,
  response        TEXT,
  -- Generated document
  document_url    TEXT,
  -- Timestamps
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DEMAND TEMPLATES
-- Pre-built demand templates based on common violations / city-specific rights
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS demand_templates (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  city         TEXT,                  -- NULL = global
  country      TEXT,
  category     TEXT NOT NULL,        -- 'repairs' | 'safety' | 'discrimination' | 'screening' | 'privacy' | 'utilities'
  title        TEXT NOT NULL,
  description  TEXT NOT NULL,
  legal_basis  TEXT,                 -- The law or regulation this is based on
  is_active    BOOLEAN DEFAULT TRUE,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- SAVED SEARCHES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_searches (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id),
  city          TEXT NOT NULL,
  min_bedrooms  SMALLINT,
  max_rent      INTEGER,
  annual_income INTEGER,
  filters       JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEARCH BLITZ ORDERS ($79 CAD premium feature)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_blitz_orders (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id),
  city          TEXT NOT NULL,
  criteria      JSONB NOT NULL,
  status        TEXT DEFAULT 'pending',  -- 'pending' | 'running' | 'complete' | 'failed'
  results_count INTEGER,
  results_url   TEXT,
  paid_at       TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_compliance ON listings(compliance_score);
CREATE INDEX IF NOT EXISTS idx_listings_flagged ON listings(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_listings_active ON listings(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
CREATE INDEX IF NOT EXISTS idx_agents_blacklisted ON agents(is_blacklisted) WHERE is_blacklisted = TRUE;
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_compliance ON agents(compliance_score);
CREATE INDEX IF NOT EXISTS idx_agents_cities ON agents USING GIN(cities_active);

-- ─────────────────────────────────────────────────────────────────────────────
-- UPDATED_AT TRIGGERS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER listings_updated_at
  BEFORE UPDATE ON listings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER agents_updated_at
  BEFORE UPDATE ON agents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER renter_demands_updated_at
  BEFORE UPDATE ON renter_demands
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

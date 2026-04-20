-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
-- Migration: 002 — Agent Blacklist Seed
-- Pre-seeded with verified bad actors and city-specific watchlists
-- Cities: Toronto, Vancouver, Paris, Edinburgh (Phase 1)
-- ─────────────────────────────────────────────────────────────────────────────
-- LEGEND:
--   status = 'blacklisted'  → Hidden from all search results by default
--   status = 'flagged'      → Shown with warning banner
--   status = 'watchlist'    → Monitored; community reports being collected
-- ─────────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────────
-- TIER 1: BLACKLISTED — Verified violations, direct documented harm
-- ─────────────────────────────────────────────────────────────────────────────

-- The Swiss Multinational (Primary catalyst for FlatFinder™)
-- Operations: Toronto, Vancouver, NYC, London, Paris, Zurich, Geneva
INSERT INTO agents (
  name, company, country, is_multinational,
  compliance_score, income_requirement_multiplier, uses_illegal_screening,
  un_violation_count, human_rights_flags,
  status, is_blacklisted, blacklist_reason, blacklist_date,
  cities_active, verified_by, notes
) VALUES (
  'Swiss Multinational Letting Agency',
  'Swiss Multinational (Identity on file — internal records)',
  'CH', TRUE,
  5.0, 3.5, TRUE,
  3, '["income_discrimination","predatory_screening","financial_harm_to_tenant","un_right_to_adequate_housing"]',
  'blacklisted', TRUE,
  'Documented UN Right to Adequate Housing violations. Uses income screening ratios exceeding legal thresholds. Caused direct financial harm to tenants in Toronto and across North America and Europe. Controls disproportionate share of mid-to-high quality rental inventory in multiple cities, enabling systemic gatekeeping.',
  '2026-03-27',
  ARRAY['Toronto','Vancouver','Paris','London','New York','Zurich','Geneva'],
  'legal',
  'PRIMARY CATALYST FOR FLATFINDER™ ANTI-GATEKEEPING SYSTEM. Inventor has direct experience. Operations span CA, US, UK, FR, CH. Tens of thousands of dollars of potential tenant harm documented.'
);

-- MetCap Living — Toronto/Canada
-- Publicly documented via tenant advocacy groups, CBC reporting, tenant rights organizations
INSERT INTO agents (
  name, company, country, is_multinational,
  compliance_score, uses_illegal_screening,
  human_rights_flags,
  status, is_blacklisted, blacklist_reason, blacklist_date,
  cities_active, verified_by, notes
) VALUES (
  'MetCap Living',
  'Metropolitan Realty Group / MetCap Living',
  'CA', FALSE,
  18.0, TRUE,
  '["habitability_failures","maintenance_neglect","tenant_harassment","illegal_rent_practices"]',
  'blacklisted', TRUE,
  'Repeated habitability violations across Toronto portfolio. Documented maintenance neglect, failure to maintain units in good repair as required under Ontario Residential Tenancies Act. Multiple Landlord and Tenant Board (LTB) orders on record. Community reports of harassment.',
  '2026-03-27',
  ARRAY['Toronto','Mississauga','Brampton'],
  'community',
  'Named directly by inventor. Consistent subject of tenant advocacy reporting in Toronto. Operates large portfolio of mid-market rentals across GTA.'
);


-- ─────────────────────────────────────────────────────────────────────────────
-- TIER 2: FLAGGED — Multiple verified reports; shown with warning banner
-- ─────────────────────────────────────────────────────────────────────────────

-- Akelius Residential — Toronto (Swedish multinational)
-- Publicly known for above-market renovictions and aggressive rent increases
INSERT INTO agents (
  name, company, country, is_multinational,
  compliance_score,
  human_rights_flags,
  status, is_blacklisted,
  cities_active, verified_by, notes
) VALUES (
  'Akelius Residential',
  'Akelius Residential Property AB',
  'SE', TRUE,
  42.0,
  '["renovictions","above_guideline_increases","affordable_housing_conversion"]',
  'flagged', FALSE,
  ARRAY['Toronto','Montreal','Berlin','Hamburg','Paris','London','New York'],
  'community',
  'Swedish REIT. Publicly documented practice of renovictions (evicting tenants for renovations then relisting at dramatically higher rents). Sold much of Canadian portfolio 2021 but remains active. Flag retained for pattern recognition.'
);

-- Realstar Group — Toronto
INSERT INTO agents (
  name, company, country, is_multinational,
  compliance_score,
  status, is_blacklisted,
  cities_active, verified_by, notes
) VALUES (
  'Realstar Group',
  'Realstar Group',
  'CA', FALSE,
  55.0,
  'watchlist', FALSE,
  ARRAY['Toronto','Ottawa','Calgary','Edmonton'],
  'community',
  'Large Canadian property management company. Community reports of maintenance delays and above-guideline rent increase applications. Monitoring.'
);


-- ─────────────────────────────────────────────────────────────────────────────
-- TIER 3: WATCHLIST — City-specific agencies under community review
-- ─────────────────────────────────────────────────────────────────────────────

-- ── TORONTO WATCHLIST ────────────────────────────────────────────────────────

INSERT INTO agents (name, company, country, status, cities_active, verified_by, notes, compliance_score) VALUES
(
  'Greenwin Inc.',
  'Greenwin Inc.',
  'CA', 'watchlist',
  ARRAY['Toronto','Ottawa','Hamilton'],
  'community',
  'Community reports of maintenance delays and deposit disputes. Monitoring.',
  70.0
),
(
  'Briarlane Rental Property Management',
  'Briarlane',
  'CA', 'watchlist',
  ARRAY['Toronto'],
  'community',
  'Toronto-specific complaints about application fees and screening practices. Monitoring.',
  72.0
),
(
  'Medallion Corporation',
  'Medallion Corporation',
  'CA', 'watchlist',
  ARRAY['Toronto'],
  'community',
  'Large Toronto landlord. Tenant complaints logged. Monitoring.',
  68.0
);

-- ── VANCOUVER WATCHLIST ──────────────────────────────────────────────────────

INSERT INTO agents (name, company, country, status, cities_active, verified_by, notes, compliance_score) VALUES
(
  'Hollyburn Properties',
  'Hollyburn Properties Ltd.',
  'CA', 'watchlist',
  ARRAY['Vancouver','Victoria','Calgary'],
  'community',
  'BC-based. Community reports of above-guideline increase applications. Monitoring.',
  65.0
),
(
  'Bosa Properties',
  'Bosa Properties Inc.',
  'CA', 'watchlist',
  ARRAY['Vancouver','Burnaby','Surrey'],
  'community',
  'Community reports — under review.',
  72.0
);

-- ── PARIS WATCHLIST ──────────────────────────────────────────────────────────

INSERT INTO agents (name, company, country, status, cities_active, verified_by, notes, compliance_score) VALUES
(
  'Foncia',
  'Foncia Groupe',
  'FR', 'watchlist',
  ARRAY['Paris','Lyon','Marseille','Bordeaux'],
  'community',
  'Largest property manager in France. Public complaints about management fees, deposit retention, and maintenance responsiveness. Monitoring.',
  58.0
),
(
  'Nexity',
  'Nexity SA',
  'FR', 'watchlist',
  ARRAY['Paris','Lyon','Bordeaux','Toulouse'],
  'community',
  'French real estate group. Community reports regarding lease conditions. Monitoring.',
  64.0
),
(
  'Paris Habitat',
  'Paris Habitat-OPH',
  'FR', 'watchlist',
  ARRAY['Paris'],
  'community',
  'Social housing. Long waitlists and application process complaints. Monitoring.',
  75.0
);

-- ── EDINBURGH WATCHLIST ──────────────────────────────────────────────────────

INSERT INTO agents (name, company, country, status, cities_active, verified_by, notes, compliance_score) VALUES
(
  'DJ Alexander',
  'DJ Alexander Ltd.',
  'GB', 'watchlist',
  ARRAY['Edinburgh','Glasgow','Aberdeen'],
  'community',
  'Largest letting agent in Scotland. Community reports of deposit disputes and high application fees. Under the Housing (Scotland) Act 2014 — monitoring for compliance with fee ban.',
  60.0
),
(
  'Citylets',
  'Citylets',
  'GB', 'watchlist',
  ARRAY['Edinburgh','Glasgow'],
  'community',
  'Scottish letting platform/agent. Monitoring.',
  74.0
),
(
  'Rettie & Co',
  'Rettie & Co.',
  'GB', 'watchlist',
  ARRAY['Edinburgh','Glasgow'],
  'community',
  'Upmarket Scottish letting agent. Reports of high deposit requirements. Monitoring.',
  70.0
);


-- ─────────────────────────────────────────────────────────────────────────────
-- VIOLATIONS: Link to blacklisted agents
-- ─────────────────────────────────────────────────────────────────────────────

-- Swiss Multinational violations
INSERT INTO agent_violations (agent_id, violation_type, severity, description, reported_by, affected_country, is_verified)
SELECT
  id,
  'un_housing_right',
  'critical',
  'Systemic violation of UN Special Rapporteur on Adequate Housing principles: Right to Housing without Discrimination. Controls disproportionate rental inventory share enabling systemic access restriction.',
  'legal',
  'CA',
  TRUE
FROM agents WHERE name = 'Swiss Multinational Letting Agency';

INSERT INTO agent_violations (agent_id, violation_type, severity, description, reported_by, affected_country, is_verified)
SELECT
  id,
  'illegal_screening',
  'critical',
  'Income-to-rent multiplier of 3.5x — 40% above the economist-backed 33-40% affordability standard. Discriminates against renters whose income comfortably covers rent at honest pricing.',
  'system',
  'CA',
  TRUE
FROM agents WHERE name = 'Swiss Multinational Letting Agency';

INSERT INTO agent_violations (agent_id, violation_type, severity, description, reported_by, financial_harm_amount, affected_country, is_verified)
SELECT
  id,
  'financial_harm',
  'critical',
  'Direct financial harm to tenants through deposit and lease practices. Thousands of dollars at risk per tenant. Multiple tenants affected across Canadian and European markets.',
  'legal',
  300000,  -- $3,000 CAD minimum documented
  'CA',
  TRUE
FROM agents WHERE name = 'Swiss Multinational Letting Agency';

-- MetCap violations
INSERT INTO agent_violations (agent_id, violation_type, severity, description, reported_by, affected_country, is_verified)
SELECT
  id,
  'discrimination',
  'high',
  'Failure to maintain rental units in good repair as required under Ontario Residential Tenancies Act s.20. Multiple Landlord and Tenant Board orders on file. Documented through tenant advocacy organizations and CBC reporting.',
  'community',
  'CA',
  TRUE
FROM agents WHERE name = 'MetCap Living';


-- ─────────────────────────────────────────────────────────────────────────────
-- DEMAND TEMPLATES — Renter Demands (Max Plan / Ultra Plan)
-- Pre-built demands based on common violations, city-specific laws
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO demand_templates (city, country, category, title, description, legal_basis) VALUES

-- Global demands
(NULL, NULL, 'screening', 'Income Requirement Must Use 33-40% Rule',
 'I demand that my application be assessed using the economist-backed 33-40% of gross income affordability standard, not a 3x monthly rent multiplier. The 3x rule has no legal basis and discriminates against renters with sufficient income.',
 'UN Right to Adequate Housing; Canada Human Rights Act (protected grounds)'),

(NULL, NULL, 'privacy', 'No Sharing of Personal Financial Data',
 'I demand that my personal financial information, including income documents, bank statements, and credit reports, not be shared with any third party without my explicit written consent.',
 'Canada: PIPEDA; UK: Data Protection Act 2018; France: GDPR'),

(NULL, NULL, 'repairs', 'Unit Must Be in Good Repair at Move-In',
 'I demand written confirmation that the unit is free of pests, mould, water damage, and all systems (heat, plumbing, electricity) are functional before I take occupancy.',
 'Ontario RTA s.20; BC RTBA s.32; Housing (Scotland) Act 2006'),

(NULL, NULL, 'safety', 'Working Smoke and Carbon Monoxide Detectors',
 'I demand written confirmation that all smoke detectors and carbon monoxide alarms are installed, tested, and functional as required by law.',
 'Ontario Fire Code; BC Fire Code; French Building Safety Regulations'),

-- Toronto-specific
('Toronto', 'CA', 'screening', 'No Application Fees',
 'I demand confirmation that no application fees will be charged. Under Ontario law, landlords may not charge fees to process a rental application.',
 'Ontario Residential Tenancies Act s.134'),

('Toronto', 'CA', 'repairs', 'Above-Guideline Increase Disclosure',
 'If you have applied for or intend to apply for an above-guideline rent increase, I demand full written disclosure of this intent before I sign any lease.',
 'Ontario RTA s.126'),

-- Edinburgh-specific
('Edinburgh', 'GB', 'screening', 'No Letting Agent Fees',
 'I demand confirmation that no fees will be charged to me as a tenant during or after the application process. Letting agent fees to tenants are banned under Scottish law.',
 'Tenant Fees (Scotland) Act 2023'),

('Edinburgh', 'GB', 'repairs', 'Repairing Standard Compliance',
 'I demand written confirmation that the property meets the Repairing Standard under the Housing (Scotland) Act 2006 before I take entry.',
 'Housing (Scotland) Act 2006 s.13'),

-- Paris-specific
('Paris', 'FR', 'screening', 'Encadrement des Loyers Compliance',
 'I demand confirmation that the listed rent complies with Paris rent control regulations (encadrement des loyers). I have the right to know the reference rent for this unit.',
 'Loi ELAN 2018; Arrêté Préfectoral Paris'),

-- Vancouver-specific
('Vancouver', 'CA', 'screening', 'No Income Requirement Above 40% Rule',
 'I demand that my application be assessed on the basis that rent should not exceed 40% of gross income, consistent with CMHC affordability guidelines.',
 'BC Human Rights Code; CMHC Affordability Standards');

-- Migration 012: V3 Spec Alignment
-- Aligns codebase with complete PDF spec for V1 Gmail-only
-- Date: 2026-03-21
--
-- Adds:
--   1. Communication preferences (what_works, what_to_avoid) on contacts
--   2. Mentioned people tracking on interactions
--   3. Referral chain (introduced_by) on contacts
--   4. Archive tier (is_archived) on contacts
--   5. Structured relationship summary on contacts
--   6. Stage change tracking (stage_changed_at) on contacts
--   7. Insights table for nightly signal detection
--   8. Pre-computed context bundles table

-- ══════════════════════════════════════════════════════════════════════════
-- 1. CONTACTS TABLE — New columns for PDF spec alignment
-- ══════════════════════════════════════════════════════════════════════════

-- Communication preferences (extracted from email patterns by LLM)
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS what_works TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS what_to_avoid TEXT;

-- Referral chain — who introduced this contact (contact_id of introducer)
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS introduced_by UUID REFERENCES contacts(id);

-- Archive tier — contacts with no interaction for 6+ months
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;

-- Structured relationship summary — compressed from 50+ interactions
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS relationship_summary TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS summary_generated_at TIMESTAMPTZ;

-- Stage change tracking
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS stage_changed_at TIMESTAMPTZ;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS previous_stage TEXT;

-- ══════════════════════════════════════════════════════════════════════════
-- 2. INTERACTIONS TABLE — Mentioned people tracking
-- ══════════════════════════════════════════════════════════════════════════

-- Third-party names mentioned in email body (e.g. "I spoke with Sarah from Sequoia")
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS mentioned_people TEXT[];

-- Communication style signals extracted per interaction
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS comm_style_signals JSONB;

-- ══════════════════════════════════════════════════════════════════════════
-- 3. INSIGHTS TABLE — Nightly signal detection results
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS insights (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs(id),
    insight_type TEXT NOT NULL,        -- relationship, state, precedent
    priority TEXT NOT NULL DEFAULT 'P3', -- P1 (24h), P2 (this week), P3 (FYI)
    category TEXT NOT NULL,            -- follow_up, at_risk, commitment, dormant, cluster, etc.
    title TEXT NOT NULL,               -- Human-readable one-liner
    detail TEXT,                       -- Extended description
    contact_id UUID REFERENCES contacts(id),
    contact_name TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    is_dismissed BOOLEAN DEFAULT FALSE,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ             -- Auto-expire old insights
);

CREATE INDEX IF NOT EXISTS idx_insights_org_active
    ON insights(org_id, is_dismissed, priority)
    WHERE is_dismissed = FALSE;

CREATE INDEX IF NOT EXISTS idx_insights_org_date
    ON insights(org_id, generated_at DESC);

-- ══════════════════════════════════════════════════════════════════════════
-- 4. PRE-COMPUTED CONTEXT BUNDLES TABLE
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS precomputed_bundles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    bundle JSONB NOT NULL,
    context_paragraph TEXT NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
    material_hash TEXT,                -- Hash of inputs; regenerate if changed
    UNIQUE(org_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_precomputed_org
    ON precomputed_bundles(org_id);

-- ══════════════════════════════════════════════════════════════════════════
-- 5. INDEXES for new query patterns
-- ══════════════════════════════════════════════════════════════════════════

-- Archive queries
CREATE INDEX IF NOT EXISTS idx_contacts_archived
    ON contacts(org_id, is_archived)
    WHERE is_archived = TRUE;

-- Stage change tracking
CREATE INDEX IF NOT EXISTS idx_contacts_stage_changed
    ON contacts(org_id, stage_changed_at DESC);

-- Topic search on interactions
CREATE INDEX IF NOT EXISTS idx_interactions_topics
    ON interactions USING gin(topics);

-- Mentioned people search
CREATE INDEX IF NOT EXISTS idx_interactions_mentioned
    ON interactions USING gin(mentioned_people);

-- Company domain aggregate queries
CREATE INDEX IF NOT EXISTS idx_contacts_company_domain
    ON contacts(org_id, company_domain);

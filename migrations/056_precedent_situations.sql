-- Phase 5: L6 Root Cause Analysis — Fingerprint Matching
--
-- Per L2 spec: compress each situation into a fingerprint, compare against
-- historical situations to find what worked before.
--
-- This table stores HISTORICAL situations with their outcomes.
-- Populated automatically when a contact's stage transitions (e.g.,
-- NEEDS_ATTENTION → ACTIVE = "RECOVERED") and manually via dashboard.

CREATE TABLE IF NOT EXISTS precedent_situations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,

    -- The fingerprint (structured feature vector for matching)
    stage TEXT NOT NULL,                -- ACTIVE | WARM | NEEDS_ATTENTION | COLD | AT_RISK
    sentiment_bucket TEXT NOT NULL,     -- POSITIVE | NEUTRAL | NEGATIVE
    days_bucket TEXT NOT NULL,          -- <7 | 7-14 | 14-30 | 30-60 | >60
    entity_type TEXT,                   -- INVESTOR | CUSTOMER | PARTNER | TEAM | OTHER
    has_overdue_commit BOOLEAN DEFAULT FALSE,
    situation_category TEXT,            -- FOLLOW_UP | DEAL_STUCK | CHURN_RISK | COLD_OUTREACH | DISCOVERY
    sentiment_trend TEXT,              -- IMPROVING | STABLE | DECLINING

    -- What happened
    action_taken TEXT,                  -- what the user/agent did
    outcome TEXT NOT NULL,              -- RECOVERED | LOST | STALLED | NO_CHANGE
    outcome_days INT,                  -- how many days until outcome was observed

    -- Context
    context_summary TEXT,              -- brief description of the situation

    -- Metadata
    source TEXT DEFAULT 'auto',        -- auto (stage transition) | manual (user input)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_precedent_situations_org
    ON precedent_situations (org_id);

CREATE INDEX IF NOT EXISTS idx_precedent_situations_fingerprint
    ON precedent_situations (org_id, stage, entity_type, situation_category);

-- Enable RLS
ALTER TABLE precedent_situations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON precedent_situations;
CREATE POLICY org_isolation ON precedent_situations FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

-- Migration: Per-org context call logging for usage tracking
-- Date: 2026-03-14
-- Purpose: Track every /v1/context API call so:
--   - Agency users (Persona 3) can show clients monthly usage
--   - Founders can see how many relationship-aware decisions their agents made
--   - Future: upsell trigger when approaching plan limits

CREATE TABLE IF NOT EXISTS context_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    entity_name TEXT,
    relationship_stage TEXT,
    action_recommendation TEXT,
    confidence FLOAT,
    cache_hit BOOLEAN DEFAULT FALSE,
    called_at TIMESTAMPTZ DEFAULT NOW()
);

-- Primary query: org usage by time period
CREATE INDEX IF NOT EXISTS idx_context_calls_org_time
    ON context_calls(org_id, called_at DESC);

-- For monthly rollup queries
CREATE INDEX IF NOT EXISTS idx_context_calls_month
    ON context_calls(org_id, date_trunc('month', called_at));

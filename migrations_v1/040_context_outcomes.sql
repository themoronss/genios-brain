-- Migration 040: context_outcomes table
-- Stores feedback on context call quality for the learning loop (Phase 9)
-- Trial: stored but ignored. Hustler: passive collection. Startup: active confidence updates.

CREATE TABLE IF NOT EXISTS context_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    context_id UUID REFERENCES context_calls(id) ON DELETE SET NULL,
    contact_name TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failure', 'partial')),
    outcome_notes TEXT,
    confidence_delta FLOAT NOT NULL DEFAULT 0.0,
    applied BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_context_outcomes_org ON context_outcomes(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_context_outcomes_unapplied ON context_outcomes(applied, created_at) WHERE applied = FALSE;

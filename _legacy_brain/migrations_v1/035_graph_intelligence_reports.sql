-- Migration 035: Graph Intelligence Reports table
-- Weekly Startup-only report snapshots

CREATE TABLE IF NOT EXISTS graph_intelligence_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    summary JSONB NOT NULL DEFAULT '{}',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_gir_org_week ON graph_intelligence_reports (org_id, week_start DESC);

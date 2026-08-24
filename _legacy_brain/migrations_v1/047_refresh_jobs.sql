-- Refresh progress tracking: per-org, per-phase idempotent tracking
-- Allows nightly refresh to resume from where it stopped on crash/restart
CREATE TABLE IF NOT EXISTS refresh_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    phase VARCHAR(50) NOT NULL,
    run_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    UNIQUE(org_id, phase, run_date)
);

CREATE INDEX idx_refresh_jobs_lookup ON refresh_jobs (org_id, run_date, status);

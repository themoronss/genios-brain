-- Migration 029: Context call tracking upgrade
-- Separates internal dashboard calls from external agent API calls,
-- adds subscription tier support, and creates daily snapshots for trend charts.

-- 1. Tag context calls with source (dashboard vs api) and agent identity
ALTER TABLE context_calls ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'api';
ALTER TABLE context_calls ADD COLUMN IF NOT EXISTS agent_id TEXT;

-- 2. Subscription tier and time tracking on orgs
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'hustler';
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS time_saved_hours FLOAT DEFAULT 0.0;

-- 3. Daily snapshots for sparkline trend charts (14-day rolling window)
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    brain_health FLOAT DEFAULT 0.0,
    aer FLOAT DEFAULT 0.0,
    time_saved_hours FLOAT DEFAULT 0.0,
    context_calls_count INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_org
    ON daily_snapshots(org_id, snapshot_date DESC);

-- 4. Partial index for fast "billable API calls today" queries
CREATE INDEX IF NOT EXISTS idx_context_calls_source
    ON context_calls(org_id, source, called_at DESC);

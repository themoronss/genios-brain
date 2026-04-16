-- Phase 4: L5 Anomaly Detection (Z-score against personal baselines)
-- Per L2 spec: compare each entity to ITSELF, not global averages.

-- Rolling 90-day baseline stats per contact.
-- Recomputed every 6h by the anomaly scanner.
CREATE TABLE IF NOT EXISTS contact_baselines (
    contact_id UUID PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,

    -- Engagement baseline (interactions per week, last 90 days)
    engagement_avg REAL,             -- avg weekly interaction count
    engagement_std REAL,             -- std dev of weekly interaction count

    -- Sentiment baseline
    sentiment_avg REAL,              -- avg sentiment over 90d
    sentiment_std REAL,              -- std dev of sentiment

    -- Response time baseline
    response_time_avg_hours REAL,    -- avg response time
    response_time_std_hours REAL,    -- std dev

    -- Window metadata
    baseline_window_days INT DEFAULT 90,
    interactions_in_window INT DEFAULT 0,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contact_baselines_org
    ON contact_baselines (org_id);

-- Flagged anomalies — entities behaving unusually.
-- Each row = one anomaly event. Persisted until resolved or dismissed.
CREATE TABLE IF NOT EXISTS contact_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,

    -- What kind of anomaly
    anomaly_type TEXT NOT NULL,      -- engagement_drop | sentiment_drop | response_slowdown | gone_silent

    -- Z-score details
    engagement_z REAL,               -- z-score for engagement deviation
    sentiment_z REAL,                -- z-score for sentiment deviation
    deviation_score REAL NOT NULL,   -- combined weighted score (>0.3 = flagged)

    -- Human-readable summary (for dashboard / agent)
    summary TEXT,                    -- e.g. "Engagement dropped 2.1 std devs below normal"

    -- Status lifecycle
    status TEXT DEFAULT 'active',    -- active | resolved | dismissed
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Prevent duplicate active anomalies for same contact+type
    UNIQUE (contact_id, anomaly_type, status)
);

CREATE INDEX IF NOT EXISTS idx_contact_anomalies_org_active
    ON contact_anomalies (org_id, status)
    WHERE status = 'active';

-- Enable RLS
ALTER TABLE contact_baselines ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON contact_baselines;
CREATE POLICY org_isolation ON contact_baselines FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

ALTER TABLE contact_anomalies ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON contact_anomalies;
CREATE POLICY org_isolation ON contact_anomalies FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

-- Phase 6: Proactive Mode — scanner insights + webhook delivery
-- Per L2 spec: GeniOS fires without asking. Scanner runs every 6h,
-- generates insights, pushes to agent via webhook.

-- Enhance existing insights table with L7 synthesis fields
ALTER TABLE insights ADD COLUMN IF NOT EXISTS memory_view TEXT;      -- raw data view
ALTER TABLE insights ADD COLUMN IF NOT EXISTS genios_view TEXT;      -- analyzed intelligence view
ALTER TABLE insights ADD COLUMN IF NOT EXISTS delivery_status TEXT DEFAULT 'pending';  -- pending | delivered | failed
ALTER TABLE insights ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;
ALTER TABLE insights ADD COLUMN IF NOT EXISTS anomaly_id UUID REFERENCES contact_anomalies(id) ON DELETE SET NULL;
ALTER TABLE insights ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'proactive';  -- proactive | manual

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_insights_delivery_pending
    ON insights (org_id, delivery_status)
    WHERE delivery_status = 'pending';

-- Webhook configuration per org
CREATE TABLE IF NOT EXISTS webhook_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,                   -- HTTPS endpoint to POST to
    secret TEXT NOT NULL,                -- HMAC-SHA256 signing secret
    is_active BOOLEAN DEFAULT TRUE,
    events TEXT[] DEFAULT ARRAY['insight'],  -- which event types to deliver
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_delivery_at TIMESTAMPTZ,
    consecutive_failures INT DEFAULT 0,  -- auto-disable after 10 failures
    UNIQUE (org_id, url)
);

-- Enable RLS
ALTER TABLE webhook_config ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON webhook_config;
CREATE POLICY org_isolation ON webhook_config FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

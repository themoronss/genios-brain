-- Phase 1.6 — delivery_attempts table for webhook retry + DLQ
-- Replaces consecutive_failures auto-disable with durable per-attempt tracking.

CREATE TABLE IF NOT EXISTS delivery_attempts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    webhook_id       UUID NOT NULL REFERENCES webhook_config(id) ON DELETE CASCADE,
    insight_id       UUID REFERENCES insights(id) ON DELETE CASCADE,
    attempt_number   INT NOT NULL DEFAULT 1,
    status           TEXT NOT NULL CHECK (status IN ('pending','succeeded','failed','dead')),
    status_code      INT,
    error            TEXT,
    scheduled_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempted_at     TIMESTAMPTZ,
    next_attempt_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_pending
    ON delivery_attempts (next_attempt_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_org
    ON delivery_attempts (org_id, attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_insight
    ON delivery_attempts (insight_id);

ALTER TABLE delivery_attempts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON delivery_attempts;
CREATE POLICY org_isolation ON delivery_attempts FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

-- Phase 1, Item #3 bug 3.4: surface why a webhook was auto-disabled and when,
-- so the dashboard can show the customer "we stopped trying because…" with a
-- timestamp and the option to re-enable after they fix their endpoint.

ALTER TABLE webhook_config
    ADD COLUMN IF NOT EXISTS disabled_reason TEXT,
    ADD COLUMN IF NOT EXISTS disabled_at     TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_webhook_config_active
    ON webhook_config (org_id, is_active);

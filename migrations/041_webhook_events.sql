-- Migration 041 — webhook_events table
-- Stores inbound webhook notifications (Gmail push, etc.) for audit + dashboard display

CREATE TABLE IF NOT EXISTS webhook_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,                    -- 'gmail', 'slack', etc.
    event_type  TEXT NOT NULL,                    -- 'push_notification', 'keepalive', etc.
    payload     JSONB,
    status      TEXT NOT NULL DEFAULT 'received', -- 'received', 'processed', 'failed', 'skipped'
    error       TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_org_received
    ON webhook_events (org_id, received_at DESC);

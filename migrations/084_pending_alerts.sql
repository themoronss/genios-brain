-- Migration 084: Pending alerts queue for proactive MCP push.
--
-- The brain router writes here after every successful recommendation.
-- The MCP layer drains 1-3 alerts on EVERY tool response and includes
-- them in `response.pending_alerts[]`, which the MCP tool description
-- instructs Claude to surface naturally as "btw, brain noticed...".
--
-- This is THE proactive moment that makes GeniOS feel alive in Claude.
-- No webhooks, no separate channel — every Claude turn is a delivery
-- opportunity.

CREATE TABLE IF NOT EXISTS pending_alerts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    recommendation_id UUID      REFERENCES recommendations(id) ON DELETE SET NULL,
    insight_type    TEXT,
    contact_id      UUID        REFERENCES contacts(id) ON DELETE SET NULL,
    contact_name    TEXT,
    title           TEXT        NOT NULL,
    body            TEXT,                       -- short narrative for Claude
    suggested_action JSONB      DEFAULT '{}'::jsonb,
    priority        FLOAT       DEFAULT 0.0,
    confidence      FLOAT       DEFAULT 0.0,
    delivered       BOOLEAN     DEFAULT FALSE,
    delivered_at    TIMESTAMPTZ,
    delivered_via   TEXT,                       -- 'mcp' | 'webhook' | NULL
    expires_at      TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '4 hours'),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Hot path index — drain query is:
--   SELECT ... FROM pending_alerts
--   WHERE org_id=? AND delivered=FALSE AND expires_at>NOW()
--   ORDER BY priority DESC, created_at DESC LIMIT 3
CREATE INDEX IF NOT EXISTS idx_pending_alerts_org_undelivered
    ON pending_alerts (org_id, delivered, expires_at)
    WHERE delivered = FALSE;

-- For dashboard display + cleanup
CREATE INDEX IF NOT EXISTS idx_pending_alerts_created
    ON pending_alerts (org_id, created_at DESC);

-- Self-cleanup: delete delivered + expired rows older than 7d
-- (run nightly from any housekeeping task; fine without if storage cheap)
COMMENT ON TABLE pending_alerts IS
'Phase 4 — proactive insights queued for delivery via the next MCP response.';

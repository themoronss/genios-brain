-- Migration 058: Agent Blackboard audit log + calendar webhook token column.
--
-- Adds:
--   1. agent_activity_log   — persisted record of agent coordination events
--      (Redis is the live blackboard; this is the audit/dashboard source).
--   2. calendar_sync_state.channel_token — verifies inbound calendar push
--      is legitimate (random token sent with watch subscription).

CREATE TABLE IF NOT EXISTS agent_activity_log (
    id              BIGSERIAL PRIMARY KEY,
    org_id          UUID        NOT NULL,
    agent_id        TEXT        NOT NULL,
    contact_id      UUID,
    action          TEXT        NOT NULL,          -- draft / send / log / scan / ...
    status          TEXT        NOT NULL,          -- claimed / released / completed / conflicted
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    metadata        JSONB       DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agent_activity_org_time
    ON agent_activity_log (org_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_activity_contact
    ON agent_activity_log (contact_id, started_at DESC)
    WHERE contact_id IS NOT NULL;

-- Calendar push notifications carry an opaque channel token that we set
-- at watch-creation time; verifying it blocks spoofed pushes.
ALTER TABLE calendar_sync_state
    ADD COLUMN IF NOT EXISTS channel_token TEXT;

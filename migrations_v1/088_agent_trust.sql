-- Migration 088: per-agent trust list.
--
-- Dima's ask (transcript): "agent's allowed to accept instructions, let's
-- say from my email." Each agent can mark certain senders/callers as
-- TRUSTED — when ingest receives a message from a trusted source, the
-- interaction row is flagged so the agent code can act on instructions
-- from those senders only.
--
-- Three match modes per row: by contact_id, by exact email, or by exact
-- phone number. Minimum-viable allowlist; pattern matching (domains, etc.)
-- can come later.
--
-- Additive only. Idempotent.

BEGIN;

CREATE TABLE IF NOT EXISTS agent_trust (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    agent_uuid   UUID NOT NULL REFERENCES registered_agents(id) ON DELETE CASCADE,
    contact_id   UUID REFERENCES contacts(id) ON DELETE CASCADE,
    match_email  TEXT,
    match_phone  TEXT,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by   TEXT,

    -- exactly one match mode per row
    CHECK (
        (contact_id IS NOT NULL)::int +
        (match_email IS NOT NULL)::int +
        (match_phone IS NOT NULL)::int = 1
    )
);

CREATE INDEX IF NOT EXISTS idx_agent_trust_agent
    ON agent_trust(agent_uuid);

CREATE INDEX IF NOT EXISTS idx_agent_trust_email
    ON agent_trust(LOWER(match_email)) WHERE match_email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_trust_phone
    ON agent_trust(match_phone) WHERE match_phone IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_trust_contact
    ON agent_trust(agent_uuid, contact_id) WHERE contact_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_trust_email
    ON agent_trust(agent_uuid, LOWER(match_email)) WHERE match_email IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_trust_phone
    ON agent_trust(agent_uuid, match_phone) WHERE match_phone IS NOT NULL;

-- Mark every ingested interaction with whether the sender/caller is in the
-- agent's trust list at ingest time. (Re-evaluation can be done later by
-- a refresh job — for now, point-in-time decision.)
ALTER TABLE interactions
    ADD COLUMN IF NOT EXISTS trusted_sender BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_interactions_trusted
    ON interactions(agent_uuid, interaction_at DESC)
    WHERE trusted_sender = TRUE;

COMMIT;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'agent_trust' AND relrowsecurity = false) THEN
        ALTER TABLE agent_trust ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'agent_trust' AND policyname = 'agent_trust_org_isolation'
    ) THEN
        EXECUTE $POL$
            CREATE POLICY agent_trust_org_isolation ON agent_trust
                USING (org_id::text = (current_setting('request.jwt.claim.org_id', true)))
        $POL$;
    END IF;
END $$;

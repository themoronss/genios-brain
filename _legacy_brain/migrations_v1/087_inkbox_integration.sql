-- Migration 087: Inkbox Integration (Phase 6).
-- Per Phase 5 Agent Registry + Inkbox kickoff: customers like Inkbox push
-- email / call / SMS events into Genios per-agent over webhooks. Each agent
-- has its own mailbox + phone bound via connector_credentials.
--
-- Brain framing: Inkbox = agent body (email server, phone, vault).
-- Genios = agent brain (cross-channel context, scope, learning).
-- This migration wires the body's events into the brain's graph.
--
-- Additive only. Idempotent.

BEGIN;

-- ── 1. connector_credentials — per-agent (or workspace) data sources ─────────
-- Holds per-agent bindings (Inkbox mailbox, Inkbox phone, etc.). Workspace-
-- level rows (agent_uuid IS NULL) preserve existing Gmail/HubSpot semantics.
CREATE TABLE IF NOT EXISTS connector_credentials (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    agent_uuid    UUID REFERENCES registered_agents(id) ON DELETE CASCADE,
    source        TEXT NOT NULL,
    -- 'inkbox_email' | 'inkbox_phone' | 'inkbox_sms' | 'gmail' | 'hubspot' | ...
    metadata      JSONB DEFAULT '{}',
    -- e.g. {"mailbox_address":"sales@inkboxmail.com","phone_number":"+15550100"}
    secret_hash   TEXT,
    -- SHA-256 of the HMAC shared-secret. Raw secret is given to Inkbox once,
    -- never stored in plaintext.
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_conn_creds_agent
    ON connector_credentials(agent_uuid)
    WHERE is_active = TRUE AND agent_uuid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_conn_creds_org_source
    ON connector_credentials(org_id, source) WHERE is_active = TRUE;

-- One active connector per (agent, source) pair. NULL agent_uuid permits
-- multiple workspace-level rows for the same source (e.g. multi-Gmail).
CREATE UNIQUE INDEX IF NOT EXISTS uq_conn_creds_agent_source_active
    ON connector_credentials(agent_uuid, source)
    WHERE is_active = TRUE AND agent_uuid IS NOT NULL;

-- ── 2. interactions — agent_uuid + external_id + kind ────────────────────────
ALTER TABLE interactions
    ADD COLUMN IF NOT EXISTS agent_uuid       UUID REFERENCES registered_agents(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS external_id      TEXT,
    ADD COLUMN IF NOT EXISTS interaction_kind TEXT,
    -- email | call | sms — broader than legacy interaction_type
    ADD COLUMN IF NOT EXISTS source           TEXT,
    -- 'inkbox_email' | 'inkbox_phone' | 'gmail' etc. (connector source value)
    ADD COLUMN IF NOT EXISTS duration_sec     INTEGER,
    -- calls only
    ADD COLUMN IF NOT EXISTS transcript       TEXT,
    -- calls only
    ADD COLUMN IF NOT EXISTS thread_external_id TEXT;
    -- email threading via Inkbox's message_id chain

-- Idempotency: same external_id + source + org never inserts twice
CREATE UNIQUE INDEX IF NOT EXISTS uq_interactions_external
    ON interactions(org_id, source, external_id)
    WHERE external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_interactions_agent_time
    ON interactions(agent_uuid, interaction_at DESC)
    WHERE agent_uuid IS NOT NULL;

-- ── 3. ingest_events — audit log for every webhook receipt ───────────────────
-- Separate from interactions because we log even rejected/duplicate webhooks
-- for debug + replay protection.
CREATE TABLE IF NOT EXISTS ingest_events (
    id              BIGSERIAL PRIMARY KEY,
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    agent_uuid      UUID REFERENCES registered_agents(id) ON DELETE SET NULL,
    source          TEXT NOT NULL,
    external_id     TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome         TEXT NOT NULL,
    -- 'accepted' | 'duplicate' | 'rejected_signature' | 'rejected_format' | 'rejected_unknown_agent'
    interaction_id  UUID REFERENCES interactions(id) ON DELETE SET NULL,
    contact_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
    error_detail    TEXT,
    payload_bytes   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ingest_events_agent_time
    ON ingest_events(agent_uuid, received_at DESC)
    WHERE agent_uuid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ingest_events_outcome
    ON ingest_events(org_id, outcome, received_at DESC);

COMMIT;

-- ── 4. RLS on connector_credentials + ingest_events (mirrors mig 053) ────────
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'connector_credentials' AND relrowsecurity = false) THEN
        ALTER TABLE connector_credentials ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'connector_credentials' AND policyname = 'conn_creds_org_isolation'
    ) THEN
        EXECUTE $POL$
            CREATE POLICY conn_creds_org_isolation ON connector_credentials
                USING (org_id::text = (current_setting('request.jwt.claim.org_id', true)))
        $POL$;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'ingest_events' AND relrowsecurity = false) THEN
        ALTER TABLE ingest_events ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'ingest_events' AND policyname = 'ingest_events_org_isolation'
    ) THEN
        EXECUTE $POL$
            CREATE POLICY ingest_events_org_isolation ON ingest_events
                USING (org_id::text = (current_setting('request.jwt.claim.org_id', true)))
        $POL$;
    END IF;
END $$;

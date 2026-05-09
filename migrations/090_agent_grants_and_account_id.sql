-- Migration 090: Phase 12 architecture pivot.
--
-- Tools (Gmail / Calendar / Inkbox / IMAP / Phone / SMS) move to workspace
-- level. Agents stop owning tool connections directly — they're granted
-- access to a SUBSET of workspace accounts via a new grant table.
--
-- This migration is ADDITIVE ONLY:
--   1. New table: agent_account_grants
--   2. New column: interactions.account_id (link to source connector)
--   3. Indexes for read-time grant filter
--
-- Migration 091 (cleanup) handles deleting the testing-only per-agent
-- connector rows separately.

BEGIN;

-- ── 1. agent_account_grants: which workspace accounts each agent can read ──
CREATE TABLE IF NOT EXISTS agent_account_grants (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    agent_uuid   UUID NOT NULL REFERENCES registered_agents(id) ON DELETE CASCADE,
    -- account_id references oauth_tokens.id OR connector_credentials.id —
    -- which one is determined by `account_kind`.
    account_id   UUID NOT NULL,
    account_kind TEXT NOT NULL CHECK (account_kind IN ('oauth', 'connector')),
    granted_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by   TEXT,
    UNIQUE (agent_uuid, account_id, account_kind)
);

CREATE INDEX IF NOT EXISTS idx_agent_grants_agent
    ON agent_account_grants(agent_uuid);

CREATE INDEX IF NOT EXISTS idx_agent_grants_account
    ON agent_account_grants(account_id, account_kind);

-- ── 2. interactions.account_id — links each row to its source connector ────
-- NULL for legacy rows (treated as universally visible) — read-time filter
-- in scope_filter.interaction_clauses respects this back-compat.
ALTER TABLE interactions
    ADD COLUMN IF NOT EXISTS account_id UUID;

CREATE INDEX IF NOT EXISTS idx_interactions_account
    ON interactions(account_id) WHERE account_id IS NOT NULL;

-- ── 3. Backfill: existing per-agent connector rows auto-grant their owner ──
-- Preserves current customer behavior on migrate. Legacy per-agent rows
-- stay until cleanup mig 091 runs.
INSERT INTO agent_account_grants (org_id, agent_uuid, account_id, account_kind, granted_by)
SELECT cc.org_id, cc.agent_uuid, cc.id, 'connector', 'system_phase12_backfill'
FROM connector_credentials cc
WHERE cc.agent_uuid IS NOT NULL AND cc.is_active = TRUE
ON CONFLICT (agent_uuid, account_id, account_kind) DO NOTHING;

-- Same for default_agent + Gmail/Calendar OAuth — auto-grant master agent
-- so existing data stays visible to it.
INSERT INTO agent_account_grants (org_id, agent_uuid, account_id, account_kind, granted_by)
SELECT ot.org_id, o.default_agent_id, ot.id, 'oauth', 'system_phase12_backfill'
FROM oauth_tokens ot
JOIN orgs o ON o.id = ot.org_id
WHERE o.default_agent_id IS NOT NULL
ON CONFLICT (agent_uuid, account_id, account_kind) DO NOTHING;

COMMIT;

-- ── RLS on grants table ──────────────────────────────────────────────────────
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'agent_account_grants' AND relrowsecurity = false) THEN
        ALTER TABLE agent_account_grants ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'agent_account_grants' AND policyname = 'agent_grants_org_isolation'
    ) THEN
        EXECUTE $POL$
            CREATE POLICY agent_grants_org_isolation ON agent_account_grants
                USING (org_id::text = (current_setting('request.jwt.claim.org_id', true)))
        $POL$;
    END IF;
END $$;

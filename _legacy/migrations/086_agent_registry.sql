-- Migration 086: Agent Registry — IAM for AI agents.
-- Per the Agent Registry PRD: every agent gets its own key, key carries identity
-- + scope cryptographically, scope is enforced at the SQL layer (not in prompts).
--
-- Brain framing: this is the "who's allowed to read what" gate of the brain.
-- It is NOT a memory layer addition; it constrains what the brain reveals to
-- each downstream agent.
--
-- Additive only — no DROP, no DELETE. Idempotent.
--
-- Existing surface preserved:
--   • registered_agents          (mig 034) — extended in place
--   • api_keys                   (mig 034) — agent_id + scope_id columns added
--   • context_calls              — scope_hash, scope_blocked, scope_source added
--   • orgs                       — default_agent_id added (legacy keys bind here)
--
-- New tables:
--   • agent_scopes               — one policy_json per agent, versioned

BEGIN;

-- ── 1. registered_agents — extend ────────────────────────────────────────────
ALTER TABLE registered_agents
    ADD COLUMN IF NOT EXISTS status      TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_by  TEXT,
    ADD COLUMN IF NOT EXISTS edited_at   TIMESTAMPTZ DEFAULT NOW();

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'registered_agents_status_check'
    ) THEN
        ALTER TABLE registered_agents
            ADD CONSTRAINT registered_agents_status_check
            CHECK (status IN ('active','paused','archived'));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'registered_agents_slug_check'
    ) THEN
        ALTER TABLE registered_agents
            ADD CONSTRAINT registered_agents_slug_check
            CHECK (agent_id ~ '^[a-z0-9_]{2,40}$');
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_registered_agents_org_active
    ON registered_agents(org_id) WHERE status != 'archived';

-- ── 2. agent_scopes — new ────────────────────────────────────────────────────
-- One row per (agent, version). Editing a scope = new row, old row keeps
-- is_active=false. This gives us audit + rollback for free.
CREATE TABLE IF NOT EXISTS agent_scopes (
    id           BIGSERIAL PRIMARY KEY,
    agent_uuid   UUID NOT NULL REFERENCES registered_agents(id) ON DELETE CASCADE,
    org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    version      INTEGER NOT NULL DEFAULT 1,
    policy_json  JSONB NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_by   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only one active scope per agent at a time
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_scopes_active
    ON agent_scopes(agent_uuid) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_agent_scopes_org
    ON agent_scopes(org_id);

CREATE INDEX IF NOT EXISTS idx_agent_scopes_policy_gin
    ON agent_scopes USING GIN (policy_json);

-- ── 3. api_keys — bind to agent + scope ──────────────────────────────────────
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS agent_uuid UUID REFERENCES registered_agents(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS scope_id   BIGINT REFERENCES agent_scopes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_api_keys_agent
    ON api_keys(agent_uuid) WHERE agent_uuid IS NOT NULL;

-- ── 4. orgs — default_agent_id (binds the legacy primary key) ────────────────
ALTER TABLE orgs
    ADD COLUMN IF NOT EXISTS default_agent_id UUID REFERENCES registered_agents(id) ON DELETE SET NULL;

-- ── 5. context_calls — scope audit ───────────────────────────────────────────
ALTER TABLE context_calls
    ADD COLUMN IF NOT EXISTS scope_hash    TEXT,
    ADD COLUMN IF NOT EXISTS scope_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS scope_source  TEXT;  -- 'agent' | 'default' | 'legacy'

CREATE INDEX IF NOT EXISTS idx_context_calls_blocked
    ON context_calls(org_id, called_at DESC) WHERE scope_blocked = TRUE;

-- ── 6. Backfill — every existing org gets a default agent + full-scope policy ─
-- Full-scope policy = no segment whitelist, no fact_type whitelist, max age large.
-- This is the legacy/brain-key behaviour we preserve for already-issued keys.
DO $$
DECLARE
    o RECORD;
    new_agent_uuid UUID;
    new_scope_id   BIGINT;
BEGIN
    FOR o IN SELECT id FROM orgs WHERE default_agent_id IS NULL LOOP
        -- Insert default agent (slug 'default_agent', or skip if already there)
        INSERT INTO registered_agents (org_id, agent_id, name, description, status, created_at)
        VALUES (o.id, 'default_agent', 'Default Agent',
                'Auto-created. Full org access. Used by primary API key.',
                'active', NOW())
        ON CONFLICT (org_id, agent_id) DO UPDATE SET status = 'active'
        RETURNING id INTO new_agent_uuid;

        IF new_agent_uuid IS NULL THEN
            SELECT id INTO new_agent_uuid FROM registered_agents
            WHERE org_id = o.id AND agent_id = 'default_agent';
        END IF;

        -- Insert full-scope policy
        INSERT INTO agent_scopes (agent_uuid, org_id, version, policy_json, is_active, created_by)
        VALUES (new_agent_uuid, o.id, 1,
                '{"version":1,"connectors":null,"segments":null,"fact_types":null,
                  "exclude_tags":[],"max_age_days":3650,"min_confidence":0.0}'::jsonb,
                TRUE, 'system_backfill')
        ON CONFLICT DO NOTHING
        RETURNING id INTO new_scope_id;

        IF new_scope_id IS NULL THEN
            SELECT id INTO new_scope_id FROM agent_scopes
            WHERE agent_uuid = new_agent_uuid AND is_active = TRUE
            ORDER BY version DESC LIMIT 1;
        END IF;

        -- Bind org's primary key to this default agent
        UPDATE orgs SET default_agent_id = new_agent_uuid WHERE id = o.id;

        -- Bind any unbound api_keys rows to default agent + scope
        UPDATE api_keys
           SET agent_uuid = new_agent_uuid,
               scope_id   = new_scope_id
         WHERE org_id = o.id
           AND agent_uuid IS NULL;
    END LOOP;
END $$;

COMMIT;

-- ── 7. RLS — agent_scopes inherits the same policy as other tenant tables ────
-- Mig 053 enables RLS on api_keys/context_calls already. Apply to agent_scopes.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'agent_scopes' AND relrowsecurity = false) THEN
        ALTER TABLE agent_scopes ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'agent_scopes' AND policyname = 'agent_scopes_org_isolation'
    ) THEN
        EXECUTE $POL$
            CREATE POLICY agent_scopes_org_isolation ON agent_scopes
                USING (org_id::text = (current_setting('request.jwt.claim.org_id', true)))
        $POL$;
    END IF;
END $$;

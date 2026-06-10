-- Migration 034: Phase 2 — V1 canonical API support
-- Adds: tokens_used tracking, registered_agents table, api_keys table

-- Token tracking per context call
ALTER TABLE context_calls ADD COLUMN IF NOT EXISTS tokens_used INTEGER;

-- Registered agent IDs per org (plan-gated: 1/3/10 for trial/hustler/startup)
CREATE TABLE IF NOT EXISTS registered_agents (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    agent_id   TEXT NOT NULL,
    name       TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_registered_agents_org
    ON registered_agents(org_id);

-- Additional API keys per org (plan-gated: 1/1/3 for trial/hustler/startup)
-- The primary key stays in orgs.api_key; this table holds any extras.
CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    key_hash     TEXT NOT NULL UNIQUE,
    key_prefix   TEXT NOT NULL,
    name         TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    is_active    BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_api_keys_org
    ON api_keys(org_id, is_active);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash
    ON api_keys(key_hash) WHERE is_active = TRUE;

-- Migration 062: Policy rules + approvals queue.
--
-- Rules-as-data. Each rule targets an action_tier + risk_tier and declares
-- a DSL-lite JSON condition (`rule_json`) that the evaluator checks against
-- a request context dict. Matching rule dictates: allow / warn / block / require_approval.

CREATE TABLE IF NOT EXISTS policy_rules (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL,
    name            TEXT        NOT NULL,
    description     TEXT,
    action_type     TEXT        NOT NULL,          -- draft / send / schedule / writeback / *
    risk_tier       TEXT,                           -- filter by risk; NULL = any
    rule_json       JSONB       NOT NULL,          -- {condition:{...}, decision:"block"|"warn"|"allow"|"require_approval"}
    priority        INT         NOT NULL DEFAULT 100,  -- lower = higher priority
    enabled         BOOLEAN     NOT NULL DEFAULT TRUE,
    mode            TEXT        NOT NULL DEFAULT 'enforce',  -- enforce / warn_only / shadow
    version         INT         NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      TEXT,
    CONSTRAINT uq_policy_org_name UNIQUE (org_id, name)
);

CREATE INDEX IF NOT EXISTS idx_policy_org_enabled
    ON policy_rules (org_id, enabled, priority)
    WHERE enabled = TRUE;

CREATE TABLE IF NOT EXISTS approvals_queue (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL,
    action_ledger_id BIGINT     REFERENCES action_ledger(id) ON DELETE SET NULL,
    agent_id        TEXT        NOT NULL,
    action_type     TEXT        NOT NULL,
    risk_tier       TEXT        NOT NULL,
    target_ref      TEXT,
    payload         JSONB       DEFAULT '{}'::jsonb,
    triggered_rule_id UUID      REFERENCES policy_rules(id) ON DELETE SET NULL,
    status          TEXT        NOT NULL DEFAULT 'pending',  -- pending / approved / rejected / expired / auto_executed
    reason          TEXT,
    approved_by     TEXT,
    approved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approvals_org_status
    ON approvals_queue (org_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_approvals_pending
    ON approvals_queue (org_id, expires_at)
    WHERE status = 'pending';

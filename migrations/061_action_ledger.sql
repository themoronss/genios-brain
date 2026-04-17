-- Migration 061: Append-only action ledger.
--
-- Every agent-initiated action (draft, send, schedule, log_interaction, writeback)
-- is recorded here with risk_tier + outcome. Compensating / reverting actions
-- reference the original via reverted_by.

CREATE TABLE IF NOT EXISTS action_ledger (
    id              BIGSERIAL PRIMARY KEY,
    org_id          UUID        NOT NULL,
    agent_id        TEXT        NOT NULL,
    action_type     TEXT        NOT NULL,          -- draft / send / schedule / log_interaction / writeback
    risk_tier       TEXT        NOT NULL,          -- internal_read / internal_write / external_draft / external_send / irreversible
    target_type     TEXT,                           -- contact / email / event / interaction
    target_ref      TEXT,                           -- entity_name / email_id / event_id / interaction_id
    contact_id      UUID,
    payload         JSONB       DEFAULT '{}'::jsonb,
    policy_decision TEXT,                           -- allow / warn / block / require_approval
    policy_rule_id  UUID,                           -- which rule matched (if any)
    outcome         TEXT        NOT NULL DEFAULT 'pending',  -- pending / success / failed / reverted
    outcome_detail  TEXT,
    reverted_by     BIGINT,                         -- FK (self) set on compensating action
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Self-FK (nullable) for compensating-action chain
ALTER TABLE action_ledger
    ADD CONSTRAINT fk_action_reverted_by
    FOREIGN KEY (reverted_by) REFERENCES action_ledger(id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_action_org_time
    ON action_ledger (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_action_contact
    ON action_ledger (contact_id, created_at DESC)
    WHERE contact_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_action_outcome
    ON action_ledger (org_id, outcome, created_at DESC);

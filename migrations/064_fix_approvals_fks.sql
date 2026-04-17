-- Migration 064: Make approvals_queue FKs deletion-safe.
--
-- The original constraints from migration 062 had no ON DELETE clause, so
-- deleting a policy_rule or action_ledger row that any approvals_queue row
-- ever referenced would fail with 23503 FK violation. Operators can't clean
-- up old test rules without manual SQL.
--
-- Fix: rewrite both FKs with ON DELETE SET NULL. The approvals row stays
-- around for audit; the pointer just becomes NULL.

ALTER TABLE approvals_queue
    DROP CONSTRAINT IF EXISTS approvals_queue_triggered_rule_id_fkey,
    ADD CONSTRAINT approvals_queue_triggered_rule_id_fkey
        FOREIGN KEY (triggered_rule_id) REFERENCES policy_rules(id) ON DELETE SET NULL;

ALTER TABLE approvals_queue
    DROP CONSTRAINT IF EXISTS approvals_queue_action_ledger_id_fkey,
    ADD CONSTRAINT approvals_queue_action_ledger_id_fkey
        FOREIGN KEY (action_ledger_id) REFERENCES action_ledger(id) ON DELETE SET NULL;

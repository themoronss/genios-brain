-- Migration 091: cleanup of testing-only per-agent connector rows.
--
-- Per Phase 12 architecture: connectors are workspace-level only. The
-- existing per-agent rows in `connector_credentials` (where agent_uuid IS
-- NOT NULL) were created during testing and should be removed before going
-- live. Mig 090 already auto-granted these to their respective agents via
-- the new grants table, so no functional regression.
--
-- This DELETE is destructive — RUN ONLY when ready to cut over to the
-- workspace-only model. Migration 090 must run first.
--
-- After this runs:
--   * connector_credentials only contains workspace rows (agent_uuid IS NULL)
--   * agent_account_grants is the single source of truth for "which agent
--     can read which account"
--
-- Schema column `connector_credentials.agent_uuid` is KEPT (nullable) for
-- audit / forensics — empty in practice.

BEGIN;

-- 1. Delete agent_account_grants pointing at per-agent connector rows
--    we're about to drop (since the connector itself is going).
DELETE FROM agent_account_grants
WHERE account_kind = 'connector'
  AND account_id IN (
      SELECT id FROM connector_credentials WHERE agent_uuid IS NOT NULL
  );

-- 2. Delete the per-agent connector rows themselves.
DELETE FROM connector_credentials WHERE agent_uuid IS NOT NULL;

-- 3. Reset interactions.account_id pointing at deleted rows (back to NULL
--    so legacy back-compat path still finds them).
UPDATE interactions SET account_id = NULL
WHERE account_id NOT IN (SELECT id FROM connector_credentials);

COMMIT;

-- Migration 089: per-agent data isolation via `data_visibility` policy field.
--
-- Phase 7 fix: scope filter currently filters contacts/facts by segment +
-- fact_type, but ingested interactions (tagged with `agent_uuid`) leak
-- across agents who share contacts. Two visibility modes:
--
--   'own'  → agent only sees interactions tagged with its own agent_uuid
--           (or untagged interactions like Gmail OAuth at workspace level)
--   'all'  → no agent_uuid filter — master/admin agent sees everything
--
-- Defaults:
--   default_agent → 'all'  (the master / admin / brain key)
--   all others     → 'own' (scoped agents)
--
-- Idempotent — re-running this migration is a no-op for already-set values.

BEGIN;

UPDATE agent_scopes asc_
SET policy_json = jsonb_set(
        policy_json,
        '{data_visibility}',
        to_jsonb('all'::text),
        true
    )
FROM registered_agents ra
WHERE asc_.agent_uuid = ra.id
  AND ra.agent_id = 'default_agent'
  AND (asc_.policy_json ? 'data_visibility') IS NOT TRUE;

UPDATE agent_scopes asc_
SET policy_json = jsonb_set(
        policy_json,
        '{data_visibility}',
        to_jsonb('own'::text),
        true
    )
FROM registered_agents ra
WHERE asc_.agent_uuid = ra.id
  AND ra.agent_id != 'default_agent'
  AND (asc_.policy_json ? 'data_visibility') IS NOT TRUE;

COMMIT;

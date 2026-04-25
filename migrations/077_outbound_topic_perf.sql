-- Migration 077 — indexes for campaign-aware context
--
-- Backs two new read paths:
--   1. get_related_outbound() — cross-contact "what else did I send on topic X"
--   2. active_campaign detector — last 72h outbound grouped by topic overlap
--
-- Uses CREATE INDEX CONCURRENTLY so index builds don't block writes on the
-- interactions table (which receives live Gmail/Calendar webhook inserts).
-- CONCURRENTLY cannot run inside a transaction — the runner must open each
-- statement with AUTOCOMMIT. See scripts/run_migration_077.py.
--
-- Rollback = DROP INDEX CONCURRENTLY (same semantics, no lock).

-- Partial index: narrow, only outbound rows. Campaign detector +
-- related_outbound always WHERE direction='outbound', so filtering at the
-- index level keeps it tiny vs the full interactions table.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interactions_org_outbound_time
  ON interactions (org_id, interaction_at DESC)
  WHERE direction = 'outbound';

-- GIN on topics TEXT[] for fast array-overlap (topics && :topics_array).
-- interactions.topics already populated by extraction pipeline (migration 004b).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interactions_topics_gin
  ON interactions USING GIN (topics);

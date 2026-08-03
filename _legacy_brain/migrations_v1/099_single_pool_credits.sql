-- Migration 099 — Single-pool credit model + Sonnet daily cap
--
-- Why: 3 separate buckets (context / sync / proactive) confused customers
--      ("balance kyun gira, maine kuch nahi kiya"). Hybrid model is:
--      • ONE visible credit balance (sum of all activity)
--      • Background ops bill 0 credits (already enforced via
--        app.credits.billing_context.is_billing_enabled — see llm/client.py)
--      • Weighted costs per operation (chat=1, draft=2, sonnet=3, ingest=1)
--
-- This migration:
--   1. Adds `orgs.credits` and `orgs.topup_credits` (single pool).
--   2. Backfills both by summing the legacy 3-bucket columns.
--   3. Adds `sonnet_daily_count` + `sonnet_daily_reset_at` for the
--      per-tier Sonnet abuse cap (Early=50/day, Startup=500/day).
--   4. KEEPS the legacy columns (context_credits/sync_credits/proactive_credits)
--      so any in-flight readers don't break — they're now unused but harmless.
--      A later migration will DROP them once code is fully migrated.
--
-- Idempotency: ALTER ... IF NOT EXISTS + WHERE balance not yet seeded so
-- re-running is safe.

BEGIN;

-- ── Single pool columns ─────────────────────────────────────────────────────
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS credits       BIGINT NOT NULL DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS topup_credits BIGINT NOT NULL DEFAULT 0;

-- ── Sonnet abuse cap tracking ───────────────────────────────────────────────
-- Reset is daily; cap is enforced by app.llm.client._check_sonnet_cap. We
-- store the count + the last reset boundary so we can wrap at midnight UTC
-- without a separate scheduled job.
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS sonnet_daily_count    INT NOT NULL DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS sonnet_daily_reset_at TIMESTAMPTZ;

-- ── Backfill single pool from legacy 3 buckets ──────────────────────────────
-- Sum context + sync + proactive into the unified pool. Only runs on rows
-- where credits is still 0 (the default), so re-running is a no-op for orgs
-- that already have a pool balance.
UPDATE orgs
SET
    credits = COALESCE(context_credits, 0)
            + COALESCE(sync_credits, 0)
            + COALESCE(proactive_credits, 0),
    topup_credits = COALESCE(topup_context_credits, 0)
                  + COALESCE(topup_sync_credits, 0)
WHERE credits = 0
  AND ( COALESCE(context_credits, 0)
      + COALESCE(sync_credits, 0)
      + COALESCE(proactive_credits, 0)
      + COALESCE(topup_context_credits, 0)
      + COALESCE(topup_sync_credits, 0) ) > 0;

-- ── Ledger row for the rebucket so reconciliation stays clean ───────────────
-- Each org that had legacy balances gets one 'grant' row in the new 'credits'
-- bucket. Idempotency key prevents re-insert on migration retry.
INSERT INTO credit_ledger
    (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
SELECT
    id,
    'credits',                         -- new single-pool bucket name
    'grant',
    credits + topup_credits,           -- total balance from legacy sum
    credits + topup_credits,
    'migration_099_rebucket',
    'mig099:rebucket:' || id::text
FROM orgs
WHERE credits + topup_credits > 0
  AND NOT EXISTS (
      SELECT 1 FROM credit_ledger
      WHERE org_id = orgs.id
        AND idempotency_key = 'mig099:rebucket:' || orgs.id::text
  );

-- Index on credits for fast quota lookups (low cardinality, OK as B-tree).
CREATE INDEX IF NOT EXISTS idx_orgs_credits ON orgs (credits);

COMMIT;

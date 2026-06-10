-- Migration 098 — Credit-based billing system
-- Adds: credit balance on orgs, immutable credit_ledger, atomic deduct support,
--       new plan tier names (trial/early/startup/enterprise).
--
-- Design:
--   • orgs.context_credits      : reactive bucket (chat / draft / user queries)
--   • orgs.sync_credits         : data ingest bucket (per email/event/message)
--   • orgs.proactive_credits    : background AI bucket (hidden from UI, internal cap)
--   • orgs.credit_period_start  : current billing period start
--   • orgs.credit_period_end    : current billing period end (= plan_expires_at typically)
--   • orgs.grace_until          : after plan_expires_at, soft-block window (read+light only)
--   • credit_ledger             : immutable append-only log of every deduct/refund/grant/topup
--   • idempotency_key UNIQUE    : retries / replays cannot double-charge
--
-- Atomic deduct pattern (enforced in app/credits/ledger.py):
--   UPDATE orgs
--      SET context_credits = context_credits - :cost
--    WHERE id = :org AND context_credits >= :cost
--   RETURNING context_credits;
--   -- 0 rows returned → insufficient credits → 402
--
-- Refunds = ledger inserts with positive amount + matching reverses_ledger_id.

BEGIN;

-- ── orgs: credit balances + grace period ─────────────────────────────────────
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS context_credits      BIGINT NOT NULL DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS sync_credits         BIGINT NOT NULL DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS proactive_credits    BIGINT NOT NULL DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS credit_period_start  TIMESTAMPTZ;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS credit_period_end    TIMESTAMPTZ;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS grace_until          TIMESTAMPTZ;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS topup_context_credits BIGINT NOT NULL DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS topup_sync_credits    BIGINT NOT NULL DEFAULT 0;

-- Concurrency note: all writes to credit columns MUST go through the atomic
-- UPDATE...WHERE balance >= cost pattern. Never SELECT-then-UPDATE.

-- ── credit_ledger: immutable transaction log ─────────────────────────────────
CREATE TABLE IF NOT EXISTS credit_ledger (
    id                  BIGSERIAL PRIMARY KEY,
    org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bucket              TEXT NOT NULL,            -- 'context' | 'sync' | 'proactive'
    kind                TEXT NOT NULL,            -- 'deduct' | 'refund' | 'grant' | 'topup' | 'reset'
    amount              BIGINT NOT NULL,          -- positive = credit added, negative = deducted
    balance_after       BIGINT NOT NULL,          -- balance for this bucket after this op
    reason              TEXT NOT NULL,            -- e.g. 'llm_call:classify_email', 'gmail_sync:record'
    related_kind        TEXT,                     -- 'llm_usage' | 'interaction' | 'subscription' | NULL
    related_id          TEXT,                     -- FK-ish pointer (text to allow uuid + bigint)
    agent_uuid          UUID,                     -- per-agent attribution (Inkbox-style)
    idempotency_key     TEXT,                     -- prevents retry double-charging
    reverses_ledger_id  BIGINT REFERENCES credit_ledger(id) ON DELETE SET NULL,
    metadata            JSONB
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_org_time
    ON credit_ledger (org_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_org_bucket_kind
    ON credit_ledger (org_id, bucket, kind, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_agent
    ON credit_ledger (org_id, agent_uuid, occurred_at DESC)
    WHERE agent_uuid IS NOT NULL;

-- Idempotency: same (org, key) cannot insert twice. App layer catches the
-- unique-violation and treats it as "already processed" (return existing row).
CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_ledger_idempotency
    ON credit_ledger (org_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON credit_ledger;
CREATE POLICY org_isolation ON credit_ledger FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

-- ── Backfill: seed credits for existing orgs based on current tier ───────────
-- Trial:      500 context / 2000  sync / 1000  proactive
-- Hustler:   3000 context / 15000 sync / 5000  proactive   (legacy → mapped to "early")
-- Startup: 100000 context / 500000 sync / 50000 proactive
-- "early" is the new tier name; existing hustler orgs keep grandfathered values
-- but are renamed via app-layer mapping. No data destruction here.

UPDATE orgs
SET context_credits   = CASE COALESCE(subscription_tier, 'trial')
                          WHEN 'trial'      THEN 500
                          WHEN 'early'      THEN 10000
                          WHEN 'hustler'    THEN 3000
                          WHEN 'startup'    THEN 100000
                          WHEN 'enterprise' THEN 1000000
                          ELSE 500
                        END,
    sync_credits      = CASE COALESCE(subscription_tier, 'trial')
                          WHEN 'trial'      THEN 2000
                          WHEN 'early'      THEN 50000
                          WHEN 'hustler'    THEN 15000
                          WHEN 'startup'    THEN 500000
                          WHEN 'enterprise' THEN 5000000
                          ELSE 2000
                        END,
    proactive_credits = CASE COALESCE(subscription_tier, 'trial')
                          WHEN 'trial'      THEN 0
                          WHEN 'early'      THEN 5000
                          WHEN 'hustler'    THEN 2000
                          WHEN 'startup'    THEN 50000
                          WHEN 'enterprise' THEN 500000
                          ELSE 0
                        END,
    credit_period_start = COALESCE(credit_period_start, plan_started_at, NOW()),
    credit_period_end   = COALESCE(credit_period_end, plan_expires_at, NOW() + INTERVAL '30 days')
WHERE context_credits = 0 AND sync_credits = 0;

-- Seed ledger with the initial grant so balances reconcile.
INSERT INTO credit_ledger (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
SELECT id, 'context', 'grant', context_credits, context_credits, 'initial_seed_098', 'seed:context:' || id::text
FROM orgs
WHERE context_credits > 0
  AND NOT EXISTS (SELECT 1 FROM credit_ledger WHERE org_id = orgs.id AND bucket = 'context');

INSERT INTO credit_ledger (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
SELECT id, 'sync', 'grant', sync_credits, sync_credits, 'initial_seed_098', 'seed:sync:' || id::text
FROM orgs
WHERE sync_credits > 0
  AND NOT EXISTS (SELECT 1 FROM credit_ledger WHERE org_id = orgs.id AND bucket = 'sync');

INSERT INTO credit_ledger (org_id, bucket, kind, amount, balance_after, reason, idempotency_key)
SELECT id, 'proactive', 'grant', proactive_credits, proactive_credits, 'initial_seed_098', 'seed:proactive:' || id::text
FROM orgs
WHERE proactive_credits > 0
  AND NOT EXISTS (SELECT 1 FROM credit_ledger WHERE org_id = orgs.id AND bucket = 'proactive');

-- ── Relax subscriptions CHECK constraints for new plan names + top-up rows ───
-- Old constraints locked plan ∈ {trial,hustler,startup} and invoice_type ∈
-- {subscription,overage}. We need:
--   plan         : accept early/startup/enterprise + top-up pack ids
--   invoice_type : accept 'topup'
-- We drop and re-add as permissive. Pack ids are validated app-side
-- against TOPUP_PACKS so a strict CHECK would just duplicate that logic
-- and need updating every time we ship a new pack.

ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_plan_check;
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_invoice_type_check;

ALTER TABLE subscriptions
    ADD CONSTRAINT subscriptions_invoice_type_check
    CHECK (invoice_type IN ('subscription', 'overage', 'topup'));

COMMIT;

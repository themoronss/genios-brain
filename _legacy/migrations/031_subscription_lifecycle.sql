-- Migration 031: Subscription lifecycle fields
-- Adds trial/plan expiry tracking to orgs table.
-- No payment gateway — plan upgrades done manually via DB.
-- New registrations auto-assigned trial (5-day period).

-- Plan period tracking
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS plan_expires_at     TIMESTAMPTZ;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS plan_started_at     TIMESTAMPTZ;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS period_context_count INT DEFAULT 0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS period_reset_at     TIMESTAMPTZ;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS plan_status         TEXT DEFAULT 'active';  -- active | expired | suspended

-- Ensure subscription_tier has the right default (trial, not hustler)
ALTER TABLE orgs ALTER COLUMN subscription_tier SET DEFAULT 'trial';

-- Backfill: assign trial to all existing orgs that have no plan set or have the old default 'hustler'
-- Sets 5-day trial from NOW() for everyone without a proper plan
UPDATE orgs
SET
    subscription_tier      = 'trial',
    plan_started_at        = NOW(),
    plan_expires_at        = NOW() + INTERVAL '5 days',
    period_reset_at        = NOW() + INTERVAL '5 days',
    period_context_count   = 0,
    plan_status            = 'active'
WHERE subscription_tier IS NULL
   OR subscription_tier   = 'hustler';

-- Index for fast expiry checks (background job)
CREATE INDEX IF NOT EXISTS idx_orgs_plan_expires
    ON orgs(plan_expires_at)
    WHERE plan_status = 'active';

-- context_calls table: add period tracking column so we can join to period windows
ALTER TABLE context_calls ADD COLUMN IF NOT EXISTS period_start TIMESTAMPTZ;

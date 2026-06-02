-- Migration 075: Morning Digest support.
--
-- Additive schema for the 7am-local daily digest (BUILD-1 — brain benchmark B1
-- "Who's cooling on me?"). Scopes strictly to new columns; existing rec flow
-- and webhook delivery are untouched.
--
-- Adds to `orgs`:
--   - timezone           — IANA tz string, default 'UTC'. Digest fires when
--                          local hour = digest_hour. Null means never opt-in.
--   - digest_hour        — integer 0-23, default 7. 0-23 lets us test at
--                          non-7 hours too.
--   - digest_enabled     — bool, default TRUE. Per-tenant opt-out without
--                          nulling timezone.
--   - last_digest_sent_at — timestamp of the last digest delivery. Gates
--                          the per-day "only send once" guard.
--
-- Any webhook_config with 'digest.daily' in its `events` array receives the
-- digest. Existing webhook consumers that don't list this event are
-- UNTOUCHED — no accidental deliveries.

ALTER TABLE orgs
    ADD COLUMN IF NOT EXISTS timezone            text DEFAULT 'UTC',
    ADD COLUMN IF NOT EXISTS digest_hour         int  DEFAULT 7,
    ADD COLUMN IF NOT EXISTS digest_enabled      boolean DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS last_digest_sent_at timestamptz;

-- Range guard for digest_hour
ALTER TABLE orgs DROP CONSTRAINT IF EXISTS orgs_digest_hour_range;
ALTER TABLE orgs ADD CONSTRAINT orgs_digest_hour_range
    CHECK (digest_hour IS NULL OR (digest_hour >= 0 AND digest_hour <= 23));

-- Migration 078 — Marketing email awareness on contacts
--
-- TIER_0 (marketing/promo/newsletter) emails are intentionally NOT extracted
-- and do NOT enter the relationship graph. But the brain still benefits from
-- knowing they exist: "Acme sent 50 newsletters but 0 personal emails" is a
-- meaningful signal about whether this is a real relationship.
--
-- These columns are updated by gmail_sync TIER_0 branch only — no LLM cost,
-- no interaction row, just a lightweight counter + timestamp. Graph stays
-- clean; brain stays aware.
--
-- Idempotent (IF NOT EXISTS).

ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS marketing_email_count INT NOT NULL DEFAULT 0;

ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS last_marketing_email_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_contacts_marketing_signal
    ON contacts (org_id, marketing_email_count DESC)
    WHERE marketing_email_count > 0;

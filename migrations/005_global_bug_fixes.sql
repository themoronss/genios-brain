-- Migration: Global bug fixes for persona testing
-- Date: 2026-03-14
-- Fixes:
--   1. Add company_domain column to contacts (needed for same-person fuzzy dedup)
--   2. Add 'SOFT' status to commitments (for tentative promises like "maybe next week")

-- 1. Add company_domain to contacts for domain-based dedup
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS company_domain TEXT;

-- Backfill company_domain from existing email addresses
UPDATE contacts
SET company_domain = split_part(email, '@', 2)
WHERE company_domain IS NULL AND email LIKE '%@%';

-- Index for fast domain-based lookups (used by dedup check)
CREATE INDEX IF NOT EXISTS idx_contacts_domain ON contacts(org_id, company_domain);

-- 2. Add 'SOFT' to commitments status enum
-- PostgreSQL doesn't support ADD VALUE IF NOT EXISTS cleanly in transactions,
-- so we alter the check constraint instead

ALTER TABLE commitments DROP CONSTRAINT IF EXISTS commitments_status_check;

ALTER TABLE commitments
ADD CONSTRAINT commitments_status_check
CHECK (status IN ('OPEN', 'FULFILLED', 'OVERDUE', 'MISSED', 'SOFT'));

-- Index for soft commitment lookups
CREATE INDEX IF NOT EXISTS idx_commitments_soft ON commitments(org_id, contact_id) WHERE status = 'SOFT';

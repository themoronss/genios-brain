-- Migration 008: Multiple Gmail accounts per organization
-- Date: 2026-03-17
-- Purpose: Allow one org to connect multiple Gmail accounts.
--
-- BEFORE: UNIQUE(org_id)                  → only one Gmail account per org
-- AFTER:  UNIQUE(org_id, account_email)   → one row per Gmail account per org

-- Step 1: Add account_email column (nullable initially for existing rows)
ALTER TABLE oauth_tokens
    ADD COLUMN IF NOT EXISTS account_email VARCHAR(255);

-- Step 2: Back-fill existing rows with a placeholder so they satisfy NOT NULL later
-- (We can't know the actual email for legacy tokens without re-authing)
UPDATE oauth_tokens
    SET account_email = 'legacy@reconnect-required.com'
    WHERE account_email IS NULL;

-- Step 3: Drop the old unique constraint on org_id alone
-- The original schema declares this via "UNIQUE" on the column definition
ALTER TABLE oauth_tokens
    DROP CONSTRAINT IF EXISTS oauth_tokens_org_id_key;

-- Step 4: Add the new composite unique constraint
ALTER TABLE oauth_tokens
    ADD CONSTRAINT oauth_tokens_org_id_account_email_key
    UNIQUE (org_id, account_email);

-- Step 5: Also add entity_type column to contacts (needed by Update 2)
ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50) DEFAULT NULL;

-- Add index for fast lookup by entity type (e.g. "show me all investors")
CREATE INDEX IF NOT EXISTS idx_contacts_entity_type
    ON contacts(org_id, entity_type)
    WHERE entity_type IS NOT NULL;

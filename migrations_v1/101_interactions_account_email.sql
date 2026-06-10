-- Add account_email to interactions.
--
-- Bug: graph_builder.py and several other ingestion paths
-- INSERT into `interactions` with an `account_email` column. Migration 008
-- added the column only to `oauth_tokens` and `contacts` — `interactions`
-- was missed. First Gmail sync crashes with:
--   "column account_email of relation interactions does not exist"
-- Sync state then flips to 'error' and the UI sticks on "Syncing..." because
-- the same INSERT keeps retrying.

ALTER TABLE interactions ADD COLUMN IF NOT EXISTS account_email VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_interactions_org_account
    ON interactions (org_id, account_email)
    WHERE account_email IS NOT NULL;

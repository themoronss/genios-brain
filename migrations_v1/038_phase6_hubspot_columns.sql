-- Migration 038: Phase 6 — HubSpot + Manual Context schema fixes
-- Run: psql $DATABASE_URL -f migrations/038_phase6_hubspot_columns.sql
--
-- Safety notes:
--   - All ALTER TABLE use IF NOT EXISTS / IF EXISTS — safe to re-run
--   - UPDATEs coerce invalid values before re-adding constraints
--   - interaction_type DEFAULT corrected ('email' was set but never valid)

-- ─── contacts: CRM enrichment columns ───────────────────────────────────────

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS job_title   TEXT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS data_source TEXT DEFAULT 'gmail';
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS updated_at  TIMESTAMPTZ DEFAULT NOW();

-- ─── interactions: fix the broken 'email' default + expand type constraint ───

-- Fix: the DEFAULT was 'email' which was never in the CHECK — correct it to 'other'
ALTER TABLE interactions ALTER COLUMN interaction_type SET DEFAULT 'other';

-- Coerce any existing rows where interaction_type = 'email' → 'other'
-- (safe: 'other' is valid in all versions of the constraint)
UPDATE interactions SET interaction_type = 'other' WHERE interaction_type = 'email';

-- Expand constraint to include CRM types and 'manual'
ALTER TABLE interactions DROP CONSTRAINT IF EXISTS interactions_interaction_type_check;
ALTER TABLE interactions ADD CONSTRAINT interactions_interaction_type_check
    CHECK (interaction_type IN (
        'email_reply', 'email_one_way', 'commitment', 'meeting', 'other',
        'cc', 'slack_dm', 'slack_mention', 'jira_issue', 'file_shared', 'doc_shared',
        'crm_contact', 'crm_deal', 'manual'
    ));

-- ─── commitments: expand owner constraint ────────────────────────────────────

-- Coerce any non-conforming owner values before adding new constraint
-- (shouldn't exist, but safe guard for any manual DB edits)
UPDATE commitments SET owner = 'us' WHERE owner NOT IN ('them', 'us', 'user', 'hubspot');

ALTER TABLE commitments DROP CONSTRAINT IF EXISTS commitments_owner_check;
ALTER TABLE commitments ADD CONSTRAINT commitments_owner_check
    CHECK (owner IN ('them', 'us', 'user', 'hubspot'));

-- ─── Index for HubSpot-sourced contacts ─────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_contacts_data_source
    ON contacts(org_id, data_source)
    WHERE data_source IS NOT NULL;

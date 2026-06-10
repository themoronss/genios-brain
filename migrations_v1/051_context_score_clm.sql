-- 051: Context Score rename + CLM states + Bootstrap tracking
-- Per Context Score + CLM spec: "composite_score" is now "context_score" everywhere.

-- 1. Rename composite_score → context_score on contacts
ALTER TABLE contacts RENAME COLUMN composite_score TO context_score;

-- 2. Rename composite_score → context_score on contact_facts
ALTER TABLE contact_facts RENAME COLUMN composite_score TO context_score;

-- 3. Add CLM state column to contacts
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS clm_state TEXT DEFAULT 'active';

-- 4. Add bootstrap tracking to oauth_tokens
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS bootstrap_status TEXT DEFAULT 'live';
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS bootstrap_started_at TIMESTAMPTZ;
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS bootstrap_completed_at TIMESTAMPTZ;
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS bootstrap_email_count INTEGER DEFAULT 0;

-- 5. Recreate indexes with new column name
DROP INDEX IF EXISTS idx_contacts_composite;
DROP INDEX IF EXISTS idx_contact_facts_composite;
CREATE INDEX IF NOT EXISTS idx_contacts_context_score ON contacts(org_id, context_score DESC);
CREATE INDEX IF NOT EXISTS idx_contact_facts_context_score ON contact_facts(context_score DESC) WHERE lifecycle_state = 'ACTIVE';

-- 6. Also fix the compound index from migration 033
DROP INDEX IF EXISTS idx_contacts_composite_recent;
CREATE INDEX IF NOT EXISTS idx_contacts_context_recent
    ON contacts(org_id, context_score DESC NULLS LAST, last_interaction_at DESC NULLS LAST)
    WHERE relationship_stage IS NOT NULL;

-- 7. Backfill clm_state from freshness_score
UPDATE contacts SET clm_state = CASE
    WHEN freshness_score >= 0.90 THEN 'fresh'
    WHEN freshness_score >= 0.70 THEN 'active'
    WHEN freshness_score >= 0.45 THEN 'aging'
    WHEN freshness_score >= 0.10 THEN 'stale'
    ELSE 'archived'
END
WHERE clm_state = 'active' AND freshness_score IS NOT NULL;

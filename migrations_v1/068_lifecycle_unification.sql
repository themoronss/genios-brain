-- Phase 4.4 — lifecycle unification
-- New `lifecycle` column with 6 canonical states. Backfill from legacy
-- `lifecycle_state`. Old column dropped in Phase 6 (14-day safety rule).

ALTER TABLE contact_facts
    ADD COLUMN IF NOT EXISTS lifecycle TEXT
    CHECK (lifecycle IN ('ingest','validate','live','fade','dormant','archive'));

-- Backfill mapping (lifecycle_state → lifecycle)
UPDATE contact_facts SET lifecycle = CASE lifecycle_state
    WHEN 'EXTRACTED'  THEN 'ingest'
    WHEN 'VALIDATED'  THEN 'validate'
    WHEN 'ACTIVE'     THEN 'live'
    WHEN 'STALE'      THEN 'fade'
    WHEN 'SUPERSEDED' THEN 'archive'
    WHEN 'ARCHIVED'   THEN 'archive'
    WHEN 'DELETED'    THEN 'archive'
    ELSE 'ingest'
END
WHERE lifecycle IS NULL;

-- Default for future inserts (keep NOT NULL applied separately once all writers updated)
ALTER TABLE contact_facts ALTER COLUMN lifecycle SET DEFAULT 'ingest';

CREATE INDEX IF NOT EXISTS idx_contact_facts_lifecycle_new
    ON contact_facts (org_id, lifecycle);

-- Alias column on contacts: relationship_stage → engagement_stage (keep both for 90d)
ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS engagement_stage TEXT;

UPDATE contacts SET engagement_stage = relationship_stage
WHERE engagement_stage IS NULL AND relationship_stage IS NOT NULL;

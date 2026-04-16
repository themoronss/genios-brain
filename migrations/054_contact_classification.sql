-- Phase 3.3: Classification columns on contacts table.
-- Principle P1: ingest everything, tag at ingestion, filter at read.

-- What type of sender is this contact?
-- Values: real_person | newsletter | bot | transactional | unknown
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS classification TEXT DEFAULT 'unknown';

-- How confident is the classification (0.0–1.0)?
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS classification_confidence REAL;

-- When was this contact last classified?
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS classified_at TIMESTAMPTZ;

-- How was it classified? header | llm | behavioral | manual_override
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS classification_method TEXT;

-- User override — if set, this ALWAYS wins over automated classification.
-- NULL = no override (use automated classification)
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS classification_override TEXT;

-- Index for filtering at read time
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contacts_classification
    ON contacts (org_id, classification)
    WHERE classification IS NOT NULL;

-- Migration 003: Add LLM extraction fields for Week 2
-- Adds intent, commitments, and topics to interactions table
-- Adds relationship calculation fields to contacts table

-- Add new fields to interactions table
ALTER TABLE interactions
ADD COLUMN IF NOT EXISTS intent TEXT DEFAULT 'other',
ADD COLUMN IF NOT EXISTS commitments TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS topics TEXT[] DEFAULT '{}';

-- Add new fields to contacts table for relationship tracking
ALTER TABLE contacts
ADD COLUMN IF NOT EXISTS entity_type TEXT DEFAULT 'UNKNOWN',
ADD COLUMN IF NOT EXISTS first_interaction_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sentiment_avg FLOAT DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS topics_aggregate TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS communication_style TEXT,
ADD COLUMN IF NOT EXISTS open_commitments_count INT DEFAULT 0;

-- Update relationship_stage to have proper default
ALTER TABLE contacts
ALTER COLUMN relationship_stage SET DEFAULT 'COLD';

-- Add index for relationship stage queries
CREATE INDEX IF NOT EXISTS idx_contacts_relationship_stage ON contacts(org_id, relationship_stage);
CREATE INDEX IF NOT EXISTS idx_contacts_last_interaction ON contacts(org_id, last_interaction_at DESC);

-- Add index for intent queries
CREATE INDEX IF NOT EXISTS idx_interactions_intent ON interactions(org_id, intent);

-- Update existing contacts to set first_interaction_at
UPDATE contacts c
SET first_interaction_at = (
    SELECT MIN(interaction_at)
    FROM interactions i
    WHERE i.contact_id = c.id
)
WHERE first_interaction_at IS NULL;

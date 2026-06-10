-- Migration 013: Add category_confidence and canonical_id to contacts
-- PDF spec: "Every entity gets a category_confidence score"
-- PDF spec: "Every entity in the graph has a canonical_id" for multi-source merging

-- Add category_confidence: how confident we are about the entity_type classification
ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS category_confidence FLOAT DEFAULT 0.5;

-- Add canonical_id: stable identity for multi-source entity resolution
ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS canonical_id UUID DEFAULT gen_random_uuid();

-- Backfill canonical_id for existing contacts
UPDATE contacts SET canonical_id = gen_random_uuid() WHERE canonical_id IS NULL;

-- Index for fast canonical_id lookups (used in entity resolution)
CREATE INDEX IF NOT EXISTS idx_contacts_canonical_id ON contacts(canonical_id);

-- Index for category_confidence filtering (low confidence = needs review)
CREATE INDEX IF NOT EXISTS idx_contacts_category_confidence ON contacts(org_id, category_confidence);

-- Comment for documentation
COMMENT ON COLUMN contacts.category_confidence IS
    'Confidence score (0.0-1.0) for entity_type classification. '
    '0.95=VC domain match, 0.75=LLM investor, 0.65=keyword match, 0.50=LLM other';

COMMENT ON COLUMN contacts.canonical_id IS
    'Stable UUID for cross-source entity identity. Used for merging when multiple '
    'sources (Gmail, HubSpot, Calendar) refer to the same person.';

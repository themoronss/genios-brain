-- Migration 059: Bitemporal columns on contacts + interactions.
--
-- Enables "as-of" queries: "what did we know about X on date Y?".
-- Additive only. Existing code keeps working (defaults fill valid_from=NOW(),
-- valid_to=NULL meaning "currently valid").

ALTER TABLE contacts
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS valid_to   TIMESTAMPTZ;

ALTER TABLE interactions
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS valid_to   TIMESTAMPTZ;

-- Partial indexes keep common-case queries (valid_to IS NULL = "current") cheap.
CREATE INDEX IF NOT EXISTS idx_contacts_current
    ON contacts (org_id, id)
    WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_interactions_current
    ON interactions (org_id, contact_id, valid_from DESC)
    WHERE valid_to IS NULL;

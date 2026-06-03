-- Migration 028: Disengagement signal tracking
-- Adds columns for attachment detection, follow-up counting, and ghosting score.

-- 1. Attachment flag on interactions (outbound emails with docs/decks)
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS has_attachment BOOLEAN DEFAULT FALSE;

-- 2. Consecutive outbound count with no inbound reply in thread
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS unanswered_followup_count INTEGER DEFAULT 0;

-- 3. Index for cross-source disengagement queries (calendar + email negative signals)
CREATE INDEX IF NOT EXISTS idx_interactions_disengagement
    ON interactions (contact_id, source, direction, interaction_at DESC);

-- 4. Index for attachment ghosting detector
CREATE INDEX IF NOT EXISTS idx_interactions_attachment
    ON interactions (contact_id, direction, interaction_at)
    WHERE has_attachment = TRUE;

-- Migration 072: auto-apply for high-confidence merge candidates.
--
-- The merge_queue builds proposals (score 0.65-1.0). Humans review via
-- /v1/merge/{org_id}/queue/{id}/merge. We now also auto-apply >=0.95 matches
-- so cross-source duplicates stop polluting scoring + precedent extraction.
--
-- Adds:
--   - auto_applied_at: timestamp when the auto-merger applied this row
--   - auto_undone_at:  timestamp when a reviewer undid the auto-merge
-- Both nullable; older rows unaffected.

ALTER TABLE merge_queue
    ADD COLUMN IF NOT EXISTS auto_applied_at timestamptz,
    ADD COLUMN IF NOT EXISTS auto_undone_at  timestamptz;

-- Index for finding rows eligible for auto-apply
CREATE INDEX IF NOT EXISTS idx_merge_queue_auto_eligible
    ON merge_queue (org_id, match_score)
    WHERE status = 'pending' AND auto_applied_at IS NULL;

-- Extend status CHECK constraint to include 'undone' for the /undo endpoint
ALTER TABLE merge_queue DROP CONSTRAINT IF EXISTS merge_queue_status_check;
ALTER TABLE merge_queue ADD CONSTRAINT merge_queue_status_check
    CHECK (status = ANY (ARRAY['pending','merged','rejected','deferred','undone']::text[]));

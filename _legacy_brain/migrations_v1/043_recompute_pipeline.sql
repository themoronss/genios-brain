-- Migration 043 — Re-extract / Recompute pipeline support
-- 1. processed_version on interactions (tracks which extraction pipeline version produced the data)
-- 2. last_recomputed_at on contacts (when scores were last rebuilt)
-- 3. recompute job status on orgs

-- ── 1. Interaction processing version ──────────────────────────────────────────

ALTER TABLE interactions
ADD COLUMN IF NOT EXISTS processed_version INT DEFAULT 1;

-- Index for finding stale interactions that need re-extraction
CREATE INDEX IF NOT EXISTS idx_interactions_processed_version
ON interactions (org_id, processed_version)
WHERE source = 'gmail';

-- ── 2. Contact recompute timestamp ─────────────────────────────────────────────

ALTER TABLE contacts
ADD COLUMN IF NOT EXISTS last_recomputed_at TIMESTAMPTZ;

-- ── 3. Org-level recompute job status ──────────────────────────────────────────

ALTER TABLE orgs
ADD COLUMN IF NOT EXISTS recompute_status TEXT DEFAULT 'idle',
ADD COLUMN IF NOT EXISTS recompute_started_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS recompute_completed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS recompute_error TEXT,
ADD COLUMN IF NOT EXISTS recompute_progress JSONB;

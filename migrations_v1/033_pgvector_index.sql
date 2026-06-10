-- Migration 033: Performance indexes (pgvector embedding indexes skipped)
-- NOTE: Embeddings are 3072-dim (Gemini embedding-001).
-- pgvector HNSW and IVFFlat both cap at 2000 dims — embedding index not possible.
-- Future: switch to a 768-dim or 1536-dim model to enable vector indexing.
-- All other performance indexes below are unaffected.

-- Composite index for context bundle lookups (org + last interaction + score)
CREATE INDEX IF NOT EXISTS idx_contacts_bundle_lookup
    ON contacts(org_id, composite_score DESC NULLS LAST, last_interaction_at DESC NULLS LAST)
    WHERE is_archived IS FALSE OR is_archived IS NULL;

-- Fast plan expiry job index (already in 031, ensure exists)
CREATE INDEX IF NOT EXISTS idx_orgs_plan_expires
    ON orgs(plan_expires_at)
    WHERE plan_status = 'active';

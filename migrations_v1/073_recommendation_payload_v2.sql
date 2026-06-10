-- Migration 073: Recommendation payload v2.
--
-- Locks the richer schema from the Master Build Document:
--   - evidence[]         — source facts the recommendation is based on
--   - precedent_links[]  — matched precedent_situations that informed it
--   - suggested_action   — structured {verb, target, draft, reasoning}
--   - confidence_level   — bucket of `confidence` (low/medium/high)
--   - rationale          — human-readable "why this fires"
--
-- Additive: old consumers see new fields and ignore them. Webhook emits
-- `X-Genios-Payload-Version: 2` header for callers that want to version-gate.

ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS evidence         jsonb,
    ADD COLUMN IF NOT EXISTS precedent_links  jsonb,
    ADD COLUMN IF NOT EXISTS suggested_action jsonb,
    ADD COLUMN IF NOT EXISTS confidence_level text,
    ADD COLUMN IF NOT EXISTS rationale        text;

-- Index so webhook dispatcher / stream can filter by confidence bucket cheaply.
CREATE INDEX IF NOT EXISTS idx_recommendations_confidence_level
    ON recommendations (org_id, confidence_level)
    WHERE confidence_level IS NOT NULL;

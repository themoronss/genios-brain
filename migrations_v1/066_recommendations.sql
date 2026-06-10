-- Phase 3.1 — recommendations table
-- Output of the brain pipeline (reasoner → scorer → gate). Feedback from the
-- operator lands in (outcome, outcome_at). Webhook dispatcher reads from here
-- starting Phase 3; `insights` remains populated for legacy paths during
-- migration.

CREATE TABLE IF NOT EXISTS recommendations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    subject_entity_id   UUID,                         -- contact_id when applicable
    insight_type        TEXT NOT NULL,
    category            TEXT,
    priority            NUMERIC(4,3) NOT NULL,        -- scorer output [0,1]
    confidence          NUMERIC(4,3) NOT NULL,        -- reasoner confidence [0,1]
    title               TEXT,
    reason              TEXT,                         -- reasoner's explanation
    action              TEXT,                         -- concrete next step
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    outcome             TEXT CHECK (outcome IN ('acted','dismissed','ignored','pending') OR outcome IS NULL),
    outcome_notes       TEXT,
    outcome_at          TIMESTAMPTZ,
    idempotency_key     TEXT,                         -- from POST /v1/feedback
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at        TIMESTAMPTZ,
    cascade_used        BOOLEAN NOT NULL DEFAULT FALSE  -- true if Sonnet escalation ran
);

CREATE INDEX IF NOT EXISTS idx_recommendations_org_created
    ON recommendations (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_open
    ON recommendations (org_id) WHERE outcome IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendations_idempotency
    ON recommendations (org_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON recommendations;
CREATE POLICY org_isolation ON recommendations FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

-- Phase 3.3 — let delivery_attempts reference either legacy insights OR new recommendations.
-- Keep insight_id intact (Phase 1). Add recommendation_id; dispatcher prefers it.
ALTER TABLE delivery_attempts
    ADD COLUMN IF NOT EXISTS recommendation_id UUID REFERENCES recommendations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_delivery_attempts_rec
    ON delivery_attempts (recommendation_id);

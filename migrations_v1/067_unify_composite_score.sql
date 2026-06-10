-- Phase 4.1 — unified composite score
-- Add `score_composite` as a STORED GENERATED column on contact_facts. Formula
-- is the product of the 5 factor scores (each in [0,1]). Keep `context_score`
-- populated in parallel for 14 days, drop in Phase 6 (per migration safety rule).

ALTER TABLE contact_facts
    ADD COLUMN IF NOT EXISTS score_composite NUMERIC(5,4)
    GENERATED ALWAYS AS (
        COALESCE(freshness_score, 0)
      * COALESCE(confidence_score, 0)
      * COALESCE(consistency_score, 0)
      * COALESCE(signal_score, 0)
      * COALESCE(authority_score, 0)
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_contact_facts_score_composite
    ON contact_facts (score_composite DESC)
    WHERE lifecycle_state IN ('ACTIVE', 'VALIDATED');

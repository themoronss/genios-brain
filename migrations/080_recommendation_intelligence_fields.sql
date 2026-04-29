-- Migration 080: Recommendation intelligence fields.
--
-- Adds three columns that record HOW a recommendation was reasoned, so the
-- learning loop and audits can answer "what facts drove this, what made the
-- model uncertain, was the cascade triggered" without re-running the LLM.
--
-- Additive: existing payload v2 fields stay untouched. v1/v2 consumers that
-- ignore unknown columns continue to work.

ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS reasoning_trace   jsonb,
    ADD COLUMN IF NOT EXISTS facts_used        text[],
    ADD COLUMN IF NOT EXISTS escalation_reason text;

-- Reasoning trace shape (informal): {
--   "model": "claude-haiku-4-5-20251001",
--   "lifecycle_modifier": 0.78,
--   "escalated": true | false,
--   "trace": [{"step": "observation"|"inference"|"recommendation", "content": "..."}]
-- }

CREATE INDEX IF NOT EXISTS idx_recommendations_escalation_reason
    ON recommendations (org_id, escalation_reason)
    WHERE escalation_reason IS NOT NULL;

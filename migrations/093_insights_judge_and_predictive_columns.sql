-- Phase 1, Items #2 + #5 + #6: extend the `insights` table with judge verdict
-- (keep/dismiss decision from the LLM judge), predictive cold window, and
-- channel recommendation surfaced from the contact's interaction history.
--
-- All columns are additive. Defaults preserve backwards compatibility for any
-- row inserted before this migration runs.

ALTER TABLE insights
    ADD COLUMN IF NOT EXISTS judge_verdict           TEXT,
    ADD COLUMN IF NOT EXISTS judge_confidence        NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS judge_reasoning         TEXT,
    ADD COLUMN IF NOT EXISTS predicted_cold_in_days  INT,
    ADD COLUMN IF NOT EXISTS recommended_channel     TEXT,
    ADD COLUMN IF NOT EXISTS recommended_channel_reason TEXT;

-- Verdict is a small controlled vocabulary; CHECK keeps junk out.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'insights_judge_verdict_check'
    ) THEN
        ALTER TABLE insights
            ADD CONSTRAINT insights_judge_verdict_check CHECK (
                judge_verdict IS NULL OR judge_verdict IN (
                    'keep',
                    'dismiss_low_signal',
                    'dismiss_stale',
                    'dismiss_pattern_match',
                    'dismiss_one_way_pattern',
                    'judge_unavailable'
                )
            );
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_insights_judge_verdict
    ON insights (org_id, judge_verdict, generated_at DESC)
    WHERE judge_verdict IS NOT NULL;

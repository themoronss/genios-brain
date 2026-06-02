-- Phase 1, Item #3 bug 3.5: prevent duplicate pending attempts when two
-- workers race on schedule_for_insights / schedule_for_recommendations.
--
-- Partial unique index only constrains 'pending' rows; 'succeeded', 'failed',
-- and 'dead' rows can have repeated keys (they're history, not state).

CREATE UNIQUE INDEX IF NOT EXISTS idx_delivery_attempts_insight_pending_unique
    ON delivery_attempts (insight_id, webhook_id, attempt_number)
    WHERE status = 'pending' AND insight_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_delivery_attempts_recommendation_pending_unique
    ON delivery_attempts (recommendation_id, webhook_id, attempt_number)
    WHERE status = 'pending' AND recommendation_id IS NOT NULL;

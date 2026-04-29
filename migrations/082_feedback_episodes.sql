-- Migration 082: Feedback episodes — natural-language outcomes for the graph.
--
-- When an agent (or human) records feedback on a recommendation, GeniOS
-- writes a natural-language "episode" describing what happened. These
-- episodes feed:
--   - The precedent harvest (Sprint 3) — pattern-matches future situations
--   - The calibration loop — labeled signal for Platt scaling
--   - The /v1/context bundle — recent episodes show the LLM what worked
--
-- Pattern is from MiroFish's ZepGraphMemoryUpdater.to_episode_text().

CREATE TABLE IF NOT EXISTS feedback_episodes (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            uuid NOT NULL,
    contact_id        uuid,                         -- nullable: feedback may pre-date contact resolution
    recommendation_id uuid NOT NULL,
    insight_type      text,
    outcome           text NOT NULL,                -- acted | dismissed | ignored
    episode_text      text NOT NULL,                -- natural-language description
    created_at        timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (recommendation_id)                      -- one episode per recommendation
);

CREATE INDEX IF NOT EXISTS idx_feedback_episodes_org_contact
    ON feedback_episodes (org_id, contact_id, created_at DESC);

-- Useful for precedent harvesting by insight_type.
CREATE INDEX IF NOT EXISTS idx_feedback_episodes_type_outcome
    ON feedback_episodes (org_id, insight_type, outcome);

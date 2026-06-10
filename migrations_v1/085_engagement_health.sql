-- Migration 085: Engagement health snapshot per org.
--
-- Daily snapshot consumed by the churn_risk detector. Composite churn_score
-- combines:
--   • hard_signals  (cancel keyword in support, billing page visit)  weight 0.5
--   • soft_signals  (api_calls drop, dismiss rate, last_login age)   weight 0.3
--   • context_signals (past complaints aligned with current friction) 0.2
--
-- Detector reads the most recent row per org. Offer composer uses the
-- breakdown to personalise its proposal.

CREATE TABLE IF NOT EXISTS engagement_health (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    snapshot_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
    api_calls_7d    INTEGER     DEFAULT 0,
    api_calls_prev_7d INTEGER   DEFAULT 0,
    dismiss_rate_30d FLOAT      DEFAULT 0.0,    -- 0.0-1.0
    last_login_at   TIMESTAMPTZ,
    sentiment_avg   FLOAT       DEFAULT 0.0,    -- avg sentiment over recent contacts
    open_complaints INTEGER     DEFAULT 0,
    sync_errors_7d  INTEGER     DEFAULT 0,
    hard_signal_score   FLOAT   DEFAULT 0.0,
    soft_signal_score   FLOAT   DEFAULT 0.0,
    context_signal_score FLOAT  DEFAULT 0.0,
    churn_score     FLOAT       DEFAULT 0.0,    -- 0.0-1.0 composite
    signals_payload JSONB       DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (org_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_engagement_health_org_date
    ON engagement_health (org_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_engagement_health_high_churn
    ON engagement_health (churn_score DESC, snapshot_date DESC)
    WHERE churn_score >= 0.5;

COMMENT ON TABLE engagement_health IS
'Phase 6 — daily snapshot driving churn detection + retention offers.';

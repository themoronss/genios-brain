-- Migration 081: Personal baselines per contact.
--
-- Replaces population-average thresholds in detectors with per-contact EWMA
-- baselines. "27 days silence" means nothing without knowing this contact's
-- normal cadence. This table holds rolling EWMA + std for each metric so
-- detectors can compute a real z-score deviation.
--
-- One row per (org, contact, metric). Refreshed nightly by
-- app/tasks/baseline_writer.py. Read-only from detectors.

CREATE TABLE IF NOT EXISTS personal_baselines (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL,
    contact_id    uuid NOT NULL,
    metric        text NOT NULL,         -- e.g. 'response_hours' | 'email_words' | 'sentiment'
    value         numeric(10,3) NOT NULL,    -- current EWMA mean
    stddev        numeric(10,3) NOT NULL DEFAULT 0,  -- rolling std for z-score
    samples       int NOT NULL DEFAULT 0,     -- count contributing to the EWMA
    updated_at    timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, contact_id, metric)
);

-- Detectors filter by (org, contact, metric); index supports the hot read path.
CREATE INDEX IF NOT EXISTS idx_personal_baselines_lookup
    ON personal_baselines (org_id, contact_id, metric);

-- For nightly writer: find contacts whose baseline is stale.
CREATE INDEX IF NOT EXISTS idx_personal_baselines_updated
    ON personal_baselines (org_id, updated_at);

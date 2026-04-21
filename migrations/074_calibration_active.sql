-- Migration 074: per-tenant on/off for calibration → gate.
--
-- Calibration fits run for every org with enough samples, but we want to
-- turn on gate consumption per-org (canary rollout). Without this flag,
-- calibration code runs correctly but gate still uses flat thresholds.

ALTER TABLE calibration_models
    ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT false NOT NULL;

-- Index for the gate's hot-path lookup
CREATE INDEX IF NOT EXISTS idx_calibration_models_active
    ON calibration_models (org_id)
    WHERE is_active = true;

-- Phase 4.10 — calibration model storage
-- One row per org with the latest Platt-scaling fit + per-type thresholds.
-- Consumed by app/brain/gate.py to adjust push thresholds per tenant.

CREATE TABLE IF NOT EXISTS calibration_models (
    org_id              UUID PRIMARY KEY REFERENCES orgs(id) ON DELETE CASCADE,
    platt_a             NUMERIC(10,6),
    platt_b             NUMERIC(10,6),
    ece                 NUMERIC(5,4),          -- expected calibration error
    thresholds_per_type JSONB NOT NULL DEFAULT '{}'::jsonb,
    sample_count        INT NOT NULL DEFAULT 0,
    trained_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE calibration_models ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON calibration_models;
CREATE POLICY org_isolation ON calibration_models FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

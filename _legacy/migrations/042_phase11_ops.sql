-- Migration 042 — Phase 11 Operations & Reliability
-- 1. feature_flags table (emergency kill switch)
-- 2. pg_trgm extension + GIN index for fuzzy contact match
-- 3. Row-Level Security on contacts + interactions

-- ── 1. Feature flags / kill switch ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feature_flags (
    key         TEXT PRIMARY KEY,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the kill switch flag (enabled = FALSE means kill is active)
INSERT INTO feature_flags (key, enabled, description)
VALUES ('kill_switch_all', TRUE, 'Global kill switch — set to FALSE to reject all API requests immediately')
ON CONFLICT (key) DO NOTHING;

-- ── 2. pg_trgm for fuzzy contact name/email lookup ──────────────────────────

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_contacts_name_trgm
    ON contacts USING GIN (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_contacts_email_trgm
    ON contacts USING GIN (email gin_trgm_ops);

-- ── 3. Row-Level Security on contacts + interactions ────────────────────────

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE interactions ENABLE ROW LEVEL SECURITY;

-- Service role (postgres) bypasses RLS — these policies apply to anon/authenticated roles
-- protecting against direct REST API / external DB access.

DROP POLICY IF EXISTS contacts_org_isolation ON contacts;
CREATE POLICY contacts_org_isolation ON contacts
    USING (org_id::text = current_setting('app.org_id', TRUE));

DROP POLICY IF EXISTS interactions_org_isolation ON interactions;
CREATE POLICY interactions_org_isolation ON interactions
    USING (org_id::text = current_setting('app.org_id', TRUE));

-- Migration 020: Google Sheets Integration
-- Run: psql $DATABASE_URL -f migrations/020_google_sheets.sql

-- ─── Sheets Connections ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sheets_connections (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  access_token             TEXT,
  refresh_token            TEXT,
  token_expires_at         TIMESTAMPTZ,
  drive_watch_channel_id   TEXT,
  drive_watch_expiry       TIMESTAMPTZ,
  last_sync_at             TIMESTAMPTZ,
  created_at               TIMESTAMPTZ DEFAULT NOW(),
  updated_at               TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id)
);

-- ─── Sheets Spreadsheets ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sheets_spreadsheets (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  spreadsheet_id      TEXT NOT NULL,
  spreadsheet_name    TEXT,
  drive_modified_time TIMESTAMPTZ,
  sync_enabled        BOOLEAN DEFAULT TRUE,
  backfill_complete   BOOLEAN DEFAULT FALSE,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, spreadsheet_id)
);

CREATE INDEX IF NOT EXISTS idx_sheets_spreadsheets_org ON sheets_spreadsheets(org_id);

-- ─── Sheets Tab Config ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sheets_tab_config (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                    UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  spreadsheet_id            TEXT NOT NULL,
  tab_name                  TEXT NOT NULL,
  tab_gid                   TEXT,
  tab_type                  TEXT CHECK (tab_type IN ('budget_tracker', 'crm', 'approval_matrix', 'okr', 'hiring', 'unknown')),
  classification_confidence FLOAT DEFAULT 0.0,
  classification_confirmed  BOOLEAN DEFAULT FALSE,
  has_header_row            BOOLEAN DEFAULT TRUE,
  row_count                 INTEGER,
  column_count              INTEGER,
  sync_enabled              BOOLEAN DEFAULT TRUE,
  last_synced_at            TIMESTAMPTZ,
  created_at                TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, spreadsheet_id, tab_name)
);

CREATE INDEX IF NOT EXISTS idx_sheets_tab_config_org ON sheets_tab_config(org_id);
CREATE INDEX IF NOT EXISTS idx_sheets_tab_config_spreadsheet ON sheets_tab_config(org_id, spreadsheet_id);

-- ─── Sheets Column Mappings ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sheets_column_mappings (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  spreadsheet_id   TEXT NOT NULL,
  tab_name         TEXT NOT NULL,
  raw_header       TEXT NOT NULL,
  canonical_field  TEXT,
  confidence       FLOAT DEFAULT 0.0,
  confirmed_by_user BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, spreadsheet_id, tab_name, raw_header)
);

CREATE INDEX IF NOT EXISTS idx_sheets_column_mappings_tab ON sheets_column_mappings(org_id, spreadsheet_id, tab_name);

-- ─── Sheets Rows ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sheets_rows (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id         UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  spreadsheet_id TEXT NOT NULL,
  tab_name       TEXT NOT NULL,
  row_index      INTEGER NOT NULL,
  row_hash       TEXT NOT NULL,
  extracted_data JSONB DEFAULT '{}',
  person_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
  is_active      BOOLEAN DEFAULT TRUE,
  synced_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, spreadsheet_id, tab_name, row_index)
);

CREATE INDEX IF NOT EXISTS idx_sheets_rows_org ON sheets_rows(org_id, spreadsheet_id, tab_name);
CREATE INDEX IF NOT EXISTS idx_sheets_rows_person ON sheets_rows(person_id)
  WHERE person_id IS NOT NULL;

-- ─── Budget State ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_state (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  source_spreadsheet_id TEXT,
  department           TEXT NOT NULL,
  period               TEXT NOT NULL,
  budget_cap           NUMERIC,
  consumed             NUMERIC DEFAULT 0,
  owner_person_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
  is_frozen            BOOLEAN DEFAULT FALSE,
  alert_threshold      FLOAT DEFAULT 0.8,
  prev_budget_cap      NUMERIC,
  cap_changed_at       TIMESTAMPTZ,
  updated_at           TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, department, period)
);

CREATE INDEX IF NOT EXISTS idx_budget_state_org ON budget_state(org_id);
CREATE INDEX IF NOT EXISTS idx_budget_state_frozen ON budget_state(org_id, is_frozen)
  WHERE is_frozen = TRUE;

-- ─── Org OKR State ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS org_okr_state (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  source_spreadsheet_id TEXT,
  metric_name           TEXT NOT NULL,
  period                TEXT NOT NULL,
  target_value          NUMERIC,
  current_value         NUMERIC,
  owner_person_id       UUID REFERENCES contacts(id) ON DELETE SET NULL,
  updated_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, metric_name, period)
);

CREATE INDEX IF NOT EXISTS idx_org_okr_state_org ON org_okr_state(org_id);

-- ─── Sheets Policy Rules ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sheets_policy_rules (
  id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                     UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  source_spreadsheet_id      TEXT,
  source_tab_name            TEXT,
  source_row_index           INTEGER,
  rule_type                  TEXT NOT NULL,
  domain                     TEXT,
  role                       TEXT,
  min_amount                 NUMERIC,
  max_amount                 NUMERIC,
  approver_role              TEXT,
  approver_person_id         UUID REFERENCES contacts(id) ON DELETE SET NULL,
  period                     TEXT,
  extraction_confidence      FLOAT DEFAULT 0.0,
  user_confirmed             BOOLEAN DEFAULT FALSE,
  is_active                  BOOLEAN DEFAULT TRUE,
  written_to_authority_graph BOOLEAN DEFAULT FALSE,
  authority_node_id          TEXT,
  prev_max_amount            NUMERIC,
  threshold_changed_at       TIMESTAMPTZ,
  created_at                 TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, source_spreadsheet_id, source_tab_name, source_row_index)
);

CREATE INDEX IF NOT EXISTS idx_sheets_policy_rules_org ON sheets_policy_rules(org_id, is_active);
CREATE INDEX IF NOT EXISTS idx_sheets_policy_rules_unconfirmed ON sheets_policy_rules(org_id, user_confirmed)
  WHERE user_confirmed = FALSE AND is_active = TRUE;

-- Migration 018: Jira Integration
-- Run: psql $DATABASE_URL -f migrations/018_jira.sql

-- ─── Jira Connections ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jira_connections (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  atlassian_cloud_id    TEXT NOT NULL,
  site_url              TEXT,
  access_token          TEXT,
  refresh_token         TEXT,
  token_expires_at      TIMESTAMPTZ,
  webhook_id            TEXT,
  webhook_registered_at TIMESTAMPTZ,
  backfill_status       TEXT DEFAULT 'pending' CHECK (backfill_status IN ('pending', 'running', 'complete', 'error')),
  backfill_jql_cursor   TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, atlassian_cloud_id)
);

CREATE INDEX IF NOT EXISTS idx_jira_connections_org ON jira_connections(org_id);

-- ─── Jira Project Config ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jira_project_config (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  project_key         TEXT NOT NULL,
  project_name        TEXT,
  project_type        TEXT CHECK (project_type IN ('dev', 'support', 'ops', 'design')),
  terminal_statuses   JSONB DEFAULT '[]',
  active_statuses     JSONB DEFAULT '[]',
  extract_enabled     BOOLEAN DEFAULT TRUE,
  last_config_refresh TIMESTAMPTZ,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, project_key)
);

CREATE INDEX IF NOT EXISTS idx_jira_project_config_org ON jira_project_config(org_id);

-- ─── Jira User Cache ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jira_user_cache (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  atlassian_account_id  TEXT NOT NULL,
  email                 TEXT,
  display_name          TEXT,
  email_visible         BOOLEAN DEFAULT TRUE,
  person_id             UUID REFERENCES contacts(id) ON DELETE SET NULL,
  cached_at             TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, atlassian_account_id)
);

CREATE INDEX IF NOT EXISTS idx_jira_user_cache_org ON jira_user_cache(org_id);
CREATE INDEX IF NOT EXISTS idx_jira_user_cache_person ON jira_user_cache(person_id)
  WHERE person_id IS NOT NULL;

-- ─── Jira Issues ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jira_issues (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  issue_id             TEXT NOT NULL,
  issue_key            TEXT NOT NULL,
  project_key          TEXT NOT NULL,
  summary              TEXT,
  issue_type           TEXT,
  status               TEXT,
  status_category      TEXT,
  is_terminal          BOOLEAN DEFAULT FALSE,
  priority             TEXT,
  assignee_account_id  TEXT,
  assignee_person_id   UUID REFERENCES contacts(id) ON DELETE SET NULL,
  reporter_person_id   UUID REFERENCES contacts(id) ON DELETE SET NULL,
  sprint_id            TEXT,
  due_date             DATE,
  original_due_date    DATE,
  due_date_changes     INTEGER DEFAULT 0,
  story_points         FLOAT,
  labels               JSONB DEFAULT '[]',
  external_entity_ids  JSONB DEFAULT '[]',
  has_blockers         BOOLEAN DEFAULT FALSE,
  blocker_issue_keys   JSONB DEFAULT '[]',
  commitment_id        UUID REFERENCES commitments(id) ON DELETE SET NULL,
  created_at           TIMESTAMPTZ NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL,
  synced_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, issue_id)
);

CREATE INDEX IF NOT EXISTS idx_jira_issues_org ON jira_issues(org_id);
CREATE INDEX IF NOT EXISTS idx_jira_issues_project ON jira_issues(org_id, project_key);
CREATE INDEX IF NOT EXISTS idx_jira_issues_assignee ON jira_issues(assignee_person_id)
  WHERE assignee_person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jira_issues_commitment ON jira_issues(commitment_id)
  WHERE commitment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jira_issues_due ON jira_issues(org_id, due_date)
  WHERE due_date IS NOT NULL AND is_terminal = FALSE;
CREATE INDEX IF NOT EXISTS idx_jira_issues_blocker ON jira_issues(org_id, has_blockers)
  WHERE has_blockers = TRUE;

-- ─── Jira Sprints ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jira_sprints (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  sprint_id         TEXT NOT NULL,
  board_id          TEXT,
  sprint_name       TEXT,
  state             TEXT CHECK (state IN ('active', 'closed', 'future')),
  start_date        DATE,
  end_date          DATE,
  committed_issues  INTEGER DEFAULT 0,
  completed_issues  INTEGER DEFAULT 0,
  velocity_score    FLOAT,
  slip_rate         FLOAT,
  reliability_score FLOAT,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, sprint_id)
);

CREATE INDEX IF NOT EXISTS idx_jira_sprints_org ON jira_sprints(org_id, state);

-- ─── ALTER commitments: add Jira columns ────────────────────────────────────
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS jira_issue_id TEXT;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS jira_issue_key TEXT;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS jira_match_confidence FLOAT;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS jira_status TEXT;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS execution_verified BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_commitments_jira_issue ON commitments(jira_issue_id)
  WHERE jira_issue_id IS NOT NULL;

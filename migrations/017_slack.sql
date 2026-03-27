-- Migration 017: Slack Integration
-- Run: psql $DATABASE_URL -f migrations/017_slack.sql

-- ─── Slack Workspaces ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slack_workspaces (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  workspace_id     TEXT NOT NULL,
  workspace_name   TEXT,
  bot_token        TEXT,
  user_token       TEXT,
  authed_user_id   TEXT,
  authed_user_email TEXT,
  last_event_at    TIMESTAMPTZ,
  backfill_status  TEXT DEFAULT 'pending' CHECK (backfill_status IN ('pending', 'running', 'complete', 'error')),
  backfill_cursor  JSONB DEFAULT '{}',
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, workspace_id)
);

CREATE INDEX IF NOT EXISTS idx_slack_workspaces_org ON slack_workspaces(org_id);

-- ─── Slack Channel Config ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slack_channel_config (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  workspace_id  TEXT NOT NULL,
  channel_id    TEXT NOT NULL,
  channel_name  TEXT,
  channel_type  TEXT CHECK (channel_type IN ('public', 'private', 'dm', 'mpim')),
  is_external   BOOLEAN DEFAULT FALSE,
  sync_enabled  BOOLEAN DEFAULT TRUE,
  priority_tier INTEGER DEFAULT 2 CHECK (priority_tier IN (1, 2, 3)),
  last_cursor   TEXT,
  last_synced_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_slack_channel_config_org ON slack_channel_config(org_id);
CREATE INDEX IF NOT EXISTS idx_slack_channel_config_workspace ON slack_channel_config(workspace_id);

-- ─── Slack User Cache ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slack_user_cache (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  workspace_id          TEXT NOT NULL,
  slack_user_id         TEXT NOT NULL,
  email                 TEXT,
  display_name          TEXT,
  is_bot                BOOLEAN DEFAULT FALSE,
  is_external           BOOLEAN DEFAULT FALSE,
  external_workspace_id TEXT,
  person_id             UUID REFERENCES contacts(id) ON DELETE SET NULL,
  cached_at             TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, slack_user_id)
);

CREATE INDEX IF NOT EXISTS idx_slack_user_cache_org ON slack_user_cache(org_id);
CREATE INDEX IF NOT EXISTS idx_slack_user_cache_person ON slack_user_cache(person_id)
  WHERE person_id IS NOT NULL;

-- ─── Slack Messages ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slack_messages (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  workspace_id         TEXT NOT NULL,
  channel_id           TEXT NOT NULL,
  message_ts           TEXT NOT NULL,
  thread_ts            TEXT,
  is_thread_root        BOOLEAN DEFAULT FALSE,
  sender_slack_id      TEXT,
  sender_person_id     UUID REFERENCES contacts(id) ON DELETE SET NULL,
  text_content         TEXT,
  text_cleaned         TEXT,
  sentiment_score      FLOAT,
  has_commitment       BOOLEAN DEFAULT FALSE,
  commitment_text      TEXT,
  commitment_due_date  TIMESTAMPTZ,
  commitment_owner_id  UUID REFERENCES contacts(id) ON DELETE SET NULL,
  urgency_level        TEXT CHECK (urgency_level IN ('low', 'medium', 'high', 'critical')),
  entities_extracted   JSONB DEFAULT '[]',
  mentions_external    BOOLEAN DEFAULT FALSE,
  is_bot               BOOLEAN DEFAULT FALSE,
  raw_event            JSONB,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, channel_id, message_ts)
);

CREATE INDEX IF NOT EXISTS idx_slack_messages_org ON slack_messages(org_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_channel ON slack_messages(org_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_sender ON slack_messages(sender_person_id)
  WHERE sender_person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_slack_messages_commitment ON slack_messages(org_id, has_commitment)
  WHERE has_commitment = TRUE;
CREATE INDEX IF NOT EXISTS idx_slack_messages_thread ON slack_messages(workspace_id, thread_ts)
  WHERE thread_ts IS NOT NULL;

-- ─── ALTER interactions: add Slack columns ───────────────────────────────────
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS slack_channel_id TEXT;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS slack_message_ts TEXT;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS slack_thread_depth INTEGER;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS slack_message_count INTEGER;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS is_external_slack BOOLEAN DEFAULT FALSE;

-- ─── ALTER commitments: add Slack columns ────────────────────────────────────
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS source_slack_message_id UUID
  REFERENCES slack_messages(id) ON DELETE SET NULL;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS slack_channel_id TEXT;

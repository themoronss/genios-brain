-- Migration 019: Notion Integration
-- Run: psql $DATABASE_URL -f migrations/019_notion.sql

-- ─── Notion Connections ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notion_connections (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  workspace_id     TEXT NOT NULL,
  workspace_name   TEXT,
  access_token     TEXT,
  bot_id           TEXT,
  last_sync_cursor TIMESTAMPTZ,
  last_full_sync_at TIMESTAMPTZ,
  backfill_status  TEXT DEFAULT 'pending' CHECK (backfill_status IN ('pending', 'running', 'complete', 'error')),
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, workspace_id)
);

CREATE INDEX IF NOT EXISTS idx_notion_connections_org ON notion_connections(org_id);

-- ─── Notion Pages ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notion_pages (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  page_id           TEXT NOT NULL,
  parent_id         TEXT,
  page_type         TEXT CHECK (page_type IN ('page', 'database_item', 'database')),
  content_type      TEXT CHECK (content_type IN ('meeting_notes', 'sop', 'policy', 'wiki', 'project', 'unknown')),
  title             TEXT,
  url               TEXT,
  is_archived       BOOLEAN DEFAULT FALSE,
  is_template       BOOLEAN DEFAULT FALSE,
  access_denied     BOOLEAN DEFAULT FALSE,
  last_edited_time  TIMESTAMPTZ,
  last_indexed_at   TIMESTAMPTZ,
  last_edited_by_id TEXT,
  block_count       INTEGER DEFAULT 0,
  chunk_count       INTEGER DEFAULT 0,
  freshness_score   FLOAT DEFAULT 1.0,
  index_status      TEXT DEFAULT 'pending' CHECK (index_status IN ('pending', 'indexed', 'error', 'skipped')),
  index_error       TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, page_id)
);

CREATE INDEX IF NOT EXISTS idx_notion_pages_org ON notion_pages(org_id);
CREATE INDEX IF NOT EXISTS idx_notion_pages_type ON notion_pages(org_id, content_type);
CREATE INDEX IF NOT EXISTS idx_notion_pages_status ON notion_pages(org_id, index_status);
CREATE INDEX IF NOT EXISTS idx_notion_pages_edited ON notion_pages(org_id, last_edited_time DESC);

-- ─── Notion Page Chunks ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notion_page_chunks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  page_id         UUID NOT NULL REFERENCES notion_pages(id) ON DELETE CASCADE,
  chunk_index     INTEGER NOT NULL,
  section_heading TEXT,
  text_content    TEXT NOT NULL,
  token_count     INTEGER,
  pinecone_vector_id TEXT,
  embedded_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, page_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_notion_chunks_page ON notion_page_chunks(page_id);
CREATE INDEX IF NOT EXISTS idx_notion_chunks_org ON notion_page_chunks(org_id);

-- ─── Notion Policy Rules ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notion_policy_rules (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                  UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  source_page_id          UUID REFERENCES notion_pages(id) ON DELETE SET NULL,
  rule_type               TEXT NOT NULL,
  rule_text               TEXT NOT NULL,
  action_domain           TEXT,
  threshold_amount        NUMERIC,
  approver_role           TEXT,
  extracted_confidence    FLOAT DEFAULT 0.0,
  is_active               BOOLEAN DEFAULT TRUE,
  page_last_edited        TIMESTAMPTZ,
  written_to_authority_graph BOOLEAN DEFAULT FALSE,
  authority_node_id       TEXT,
  created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notion_policy_rules_org ON notion_policy_rules(org_id, is_active);

-- ─── Notion Meeting Notes ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notion_meeting_notes (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  page_id             UUID NOT NULL REFERENCES notion_pages(id) ON DELETE CASCADE,
  meeting_date        DATE,
  attendees_raw       JSONB DEFAULT '[]',
  attendee_person_ids JSONB DEFAULT '[]',
  decisions           JSONB DEFAULT '[]',
  action_items        JSONB DEFAULT '[]',
  topics              JSONB DEFAULT '[]',
  external_entities   JSONB DEFAULT '[]',
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, page_id)
);

CREATE INDEX IF NOT EXISTS idx_notion_meeting_notes_org ON notion_meeting_notes(org_id);
CREATE INDEX IF NOT EXISTS idx_notion_meeting_notes_date ON notion_meeting_notes(org_id, meeting_date DESC);

-- ─── ALTER commitments: add Notion columns ───────────────────────────────────
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS notion_page_id TEXT;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS notion_action_item_index INTEGER;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS notion_meeting_date DATE;

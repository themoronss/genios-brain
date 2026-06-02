-- Migration 022: Google Docs Integration
-- Run: psql $DATABASE_URL -f migrations/022_google_docs.sql

-- ─── GDocs Connections ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_connections (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                 UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  access_token           TEXT,
  refresh_token          TEXT,
  token_expires_at       TIMESTAMPTZ,
  drive_watch_channel_id TEXT,
  drive_watch_expiry     TIMESTAMPTZ,
  last_sync_cursor       TIMESTAMPTZ,
  last_full_sync_at      TIMESTAMPTZ,
  backfill_status        TEXT DEFAULT 'pending' CHECK (backfill_status IN ('pending', 'running', 'complete', 'error')),
  created_at             TIMESTAMPTZ DEFAULT NOW(),
  updated_at             TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id)
);

-- ─── GDocs Documents ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_documents (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  document_id              TEXT NOT NULL,
  title                    TEXT,
  doc_type                 TEXT CHECK (doc_type IN ('contract', 'proposal', 'board_report', 'sop', 'meeting_notes', 'policy', 'spec', 'other')),
  doc_type_confidence      FLOAT DEFAULT 0.0,
  owned_by_us              BOOLEAN DEFAULT FALSE,
  owner_email              TEXT,
  last_modified_time       TIMESTAMPTZ,
  last_indexed_at          TIMESTAMPTZ,
  word_count               INTEGER DEFAULT 0,
  chunk_count              INTEGER DEFAULT 0,
  comment_count            INTEGER DEFAULT 0,
  unresolved_comment_count INTEGER DEFAULT 0,
  access_denied            BOOLEAN DEFAULT FALSE,
  index_status             TEXT DEFAULT 'pending' CHECK (index_status IN ('pending', 'indexed', 'error', 'skipped')),
  index_error              TEXT,
  created_at               TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_gdocs_documents_org ON gdocs_documents(org_id);
CREATE INDEX IF NOT EXISTS idx_gdocs_documents_type ON gdocs_documents(org_id, doc_type);
CREATE INDEX IF NOT EXISTS idx_gdocs_documents_status ON gdocs_documents(org_id, index_status);
CREATE INDEX IF NOT EXISTS idx_gdocs_documents_modified ON gdocs_documents(org_id, last_modified_time DESC);

-- ─── GDocs Chunks ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_chunks (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  document_id        UUID NOT NULL REFERENCES gdocs_documents(id) ON DELETE CASCADE,
  chunk_index        INTEGER NOT NULL,
  section_heading    TEXT,
  text_content       TEXT NOT NULL,
  token_count        INTEGER,
  pinecone_vector_id TEXT,
  embedded_at        TIMESTAMPTZ,
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_gdocs_chunks_document ON gdocs_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_gdocs_chunks_org ON gdocs_chunks(org_id);

-- ─── GDocs Comments ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_comments (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                  UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  document_id             UUID NOT NULL REFERENCES gdocs_documents(id) ON DELETE CASCADE,
  comment_id              TEXT NOT NULL,
  author_email            TEXT,
  author_person_id        UUID REFERENCES contacts(id) ON DELETE SET NULL,
  content                 TEXT,
  quoted_text             TEXT,
  resolved                BOOLEAN DEFAULT FALSE,
  resolved_by_email       TEXT,
  resolved_by_person_id   UUID REFERENCES contacts(id) ON DELETE SET NULL,
  comment_type            TEXT CHECK (comment_type IN ('review', 'question', 'approval', 'edit_request', 'other')),
  authority_signal_written BOOLEAN DEFAULT FALSE,
  created_at              TIMESTAMPTZ NOT NULL,
  UNIQUE(org_id, document_id, comment_id)
);

CREATE INDEX IF NOT EXISTS idx_gdocs_comments_document ON gdocs_comments(document_id);
CREATE INDEX IF NOT EXISTS idx_gdocs_comments_org ON gdocs_comments(org_id);
CREATE INDEX IF NOT EXISTS idx_gdocs_comments_author ON gdocs_comments(author_person_id)
  WHERE author_person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gdocs_comments_unresolved ON gdocs_comments(org_id, resolved)
  WHERE resolved = FALSE;

-- ─── GDocs Contracts ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_contracts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  document_id           UUID NOT NULL REFERENCES gdocs_documents(id) ON DELETE CASCADE,
  contract_type         TEXT CHECK (contract_type IN ('vendor', 'client', 'employment', 'nda', 'partnership', 'saas', 'other')),
  parties               JSONB DEFAULT '[]',
  contract_value        NUMERIC,
  currency              TEXT DEFAULT 'USD',
  effective_date        DATE,
  expiry_date           DATE,
  auto_renew            BOOLEAN DEFAULT FALSE,
  renewal_notice_days   INTEGER,
  owner_person_id       UUID REFERENCES contacts(id) ON DELETE SET NULL,
  status                TEXT DEFAULT 'active' CHECK (status IN ('draft', 'active', 'expired', 'terminated', 'renewed')),
  alert_sent_60d        BOOLEAN DEFAULT FALSE,
  alert_sent_30d        BOOLEAN DEFAULT FALSE,
  extraction_confidence FLOAT DEFAULT 0.0,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_gdocs_contracts_org ON gdocs_contracts(org_id, status);
CREATE INDEX IF NOT EXISTS idx_gdocs_contracts_expiry ON gdocs_contracts(org_id, expiry_date)
  WHERE expiry_date IS NOT NULL AND status = 'active';

-- ─── GDocs Proposals ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_proposals (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  document_id           UUID NOT NULL REFERENCES gdocs_documents(id) ON DELETE CASCADE,
  recipient_email       TEXT,
  recipient_person_id   UUID REFERENCES contacts(id) ON DELETE SET NULL,
  recipient_org         TEXT,
  pricing_summary       TEXT,
  scope_summary         TEXT,
  timeline_summary      TEXT,
  sent_date             DATE,
  proposal_status       TEXT DEFAULT 'sent' CHECK (proposal_status IN ('draft', 'sent', 'accepted', 'rejected', 'negotiating')),
  extraction_confidence FLOAT DEFAULT 0.0,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_gdocs_proposals_org ON gdocs_proposals(org_id);
CREATE INDEX IF NOT EXISTS idx_gdocs_proposals_recipient ON gdocs_proposals(recipient_person_id)
  WHERE recipient_person_id IS NOT NULL;

-- ─── GDocs Policy Rules ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdocs_policy_rules (
  id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                     UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  document_id                UUID NOT NULL REFERENCES gdocs_documents(id) ON DELETE CASCADE,
  rule_type                  TEXT NOT NULL,
  rule_text                  TEXT NOT NULL,
  action_domain              TEXT,
  step_owner_role            TEXT,
  extraction_confidence      FLOAT DEFAULT 0.0,
  written_to_authority_graph BOOLEAN DEFAULT FALSE,
  authority_node_id          TEXT,
  page_last_modified         TIMESTAMPTZ,
  is_active                  BOOLEAN DEFAULT TRUE,
  created_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdocs_policy_rules_org ON gdocs_policy_rules(org_id, is_active);
CREATE INDEX IF NOT EXISTS idx_gdocs_policy_rules_document ON gdocs_policy_rules(document_id);

-- ─── ALTER interactions: add Docs columns ────────────────────────────────────
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS gdocs_document_id TEXT;

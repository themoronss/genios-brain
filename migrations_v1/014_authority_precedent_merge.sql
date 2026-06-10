-- Migration 014: Authority Graph, Precedent Graph, Merge Queue, Commitment Enrichment
-- Run: psql $DATABASE_URL -f migrations/014_authority_precedent_merge.sql

-- ─── Commitments: add blocker/priority columns ─────────────────────────────
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS revenue_impact BOOLEAN DEFAULT FALSE;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS is_blocker BOOLEAN DEFAULT FALSE;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'normal'
  CHECK (priority IN ('low', 'normal', 'high', 'critical'));

CREATE INDEX IF NOT EXISTS idx_commitments_is_blocker
  ON commitments(org_id, is_blocker) WHERE is_blocker = TRUE;
CREATE INDEX IF NOT EXISTS idx_commitments_priority
  ON commitments(org_id, priority);

-- ─── Authority Graph ────────────────────────────────────────────────────────
-- Role definitions within an org (CEO, CTO, Investor, Advisor, etc.)
CREATE TABLE IF NOT EXISTS authority_roles (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  role_name   TEXT NOT NULL,
  description TEXT,
  trust_level INTEGER DEFAULT 50 CHECK (trust_level BETWEEN 0 AND 100),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_authority_roles_org ON authority_roles(org_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_authority_roles_name
  ON authority_roles(org_id, role_name);

-- Permissions: what actions each role can authorize, and thresholds
CREATE TABLE IF NOT EXISTS authority_permissions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  role_id           UUID NOT NULL REFERENCES authority_roles(id) ON DELETE CASCADE,
  action_type       TEXT NOT NULL,         -- e.g. "send_email", "schedule_meeting", "commit_funds"
  max_value         NUMERIC,               -- dollar/unit threshold (NULL = unlimited)
  requires_approval BOOLEAN DEFAULT FALSE,
  escalate_to_role  UUID REFERENCES authority_roles(id),
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_authority_permissions_role ON authority_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_authority_permissions_org  ON authority_permissions(org_id);

-- Contact ↔ Role assignments
CREATE TABLE IF NOT EXISTS authority_assignments (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  contact_id  UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  role_id     UUID NOT NULL REFERENCES authority_roles(id) ON DELETE CASCADE,
  confidence  FLOAT DEFAULT 0.7,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (org_id, contact_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_authority_assignments_contact ON authority_assignments(contact_id);
CREATE INDEX IF NOT EXISTS idx_authority_assignments_org     ON authority_assignments(org_id);

-- ─── Precedent Graph ────────────────────────────────────────────────────────
-- Store past decisions + outcomes for pattern matching
CREATE TABLE IF NOT EXISTS precedent_graph (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  situation_type      TEXT NOT NULL,   -- e.g. "investor_followup", "cold_reactivation", "commitment_negotiation"
  context_summary     TEXT,
  action_taken        TEXT NOT NULL,   -- what was done
  outcome_type        TEXT,            -- "positive", "negative", "neutral", "pending"
  outcome_quality     FLOAT,           -- -1.0 to 1.0 normalized outcome score
  approval_status     TEXT DEFAULT 'approved' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
  decay_weight        FLOAT DEFAULT 1.0, -- decreases over time; formula: 0.5^(months_ago/12)
  contact_id          UUID REFERENCES contacts(id) ON DELETE SET NULL,
  related_tags        TEXT[],          -- topic tags from the situation
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  outcome_recorded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_precedent_org       ON precedent_graph(org_id);
CREATE INDEX IF NOT EXISTS idx_precedent_type      ON precedent_graph(org_id, situation_type);
CREATE INDEX IF NOT EXISTS idx_precedent_outcome   ON precedent_graph(org_id, outcome_type);
CREATE INDEX IF NOT EXISTS idx_precedent_created   ON precedent_graph(org_id, created_at DESC);

-- ─── Merge Queue ────────────────────────────────────────────────────────────
-- Entity resolution: candidate duplicate contacts for human review
CREATE TABLE IF NOT EXISTS merge_queue (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  contact_id_a UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  contact_id_b UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  match_score  FLOAT NOT NULL,   -- 0.0-1.0; higher = more likely duplicate
  match_reason TEXT,             -- e.g. "same_name_diff_domain", "same_email_variations"
  status       TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'merged', 'rejected', 'deferred')),
  reviewed_by  TEXT,             -- user email / agent id
  reviewed_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (org_id, contact_id_a, contact_id_b)
);

CREATE INDEX IF NOT EXISTS idx_merge_queue_org    ON merge_queue(org_id, status);
CREATE INDEX IF NOT EXISTS idx_merge_queue_score  ON merge_queue(org_id, match_score DESC);
CREATE INDEX IF NOT EXISTS idx_merge_queue_pending ON merge_queue(org_id) WHERE status = 'pending';

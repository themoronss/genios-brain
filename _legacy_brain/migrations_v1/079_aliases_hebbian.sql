-- Migration 079: entity aliases + Hebbian edge weights + raw_body trigram
--
-- Three additive changes, all idempotent. Safe to run on a live tenant.
--
-- 1. entity_aliases   — fuzzy contact resolution at retrieval time.
-- 2. contact_facts    — Hebbian edge weight columns (Shodh pattern):
--                       edge_weight, coactivation_count, is_potentiated,
--                       last_coactivated_at. Powers the nightly learning job.
-- 3. interactions     — GIN trigram index on raw_body so substring/fuzzy
--                       lookups against the verbatim body run cheaply.
--                       (search_tsv from mig 063 already covers full-text;
--                       this fills the substring-match gap.)
--
-- No drops. No renames. All defaults are neutral so existing queries are
-- unaffected.

-- ── 1. entity_aliases ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_aliases (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    contact_id   UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    alias_text   TEXT NOT NULL,
    alias_kind   TEXT NOT NULL,
        -- email | display_name | nickname | external_id | inferred
    confidence   NUMERIC(3,2) NOT NULL DEFAULT 1.00,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, contact_id, alias_text)
);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_text_trgm
    ON entity_aliases USING GIN (alias_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_org_lower
    ON entity_aliases (org_id, lower(alias_text));

-- Backfill from existing contacts. Idempotent via UNIQUE(org, contact, alias).
INSERT INTO entity_aliases (org_id, contact_id, alias_text, alias_kind, confidence)
SELECT org_id, id, lower(email), 'email', 1.00
FROM contacts
WHERE email IS NOT NULL AND email <> ''
ON CONFLICT (org_id, contact_id, alias_text) DO NOTHING;

INSERT INTO entity_aliases (org_id, contact_id, alias_text, alias_kind, confidence)
SELECT org_id, id, name, 'display_name', 0.95
FROM contacts
WHERE name IS NOT NULL AND name <> ''
ON CONFLICT (org_id, contact_id, alias_text) DO NOTHING;

-- ── 2. Hebbian edge weight columns on contact_facts ─────────────────────────

ALTER TABLE contact_facts
    ADD COLUMN IF NOT EXISTS edge_weight         NUMERIC(4,3) DEFAULT 0.500,
    ADD COLUMN IF NOT EXISTS coactivation_count  INT          DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_potentiated      BOOLEAN      DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_coactivated_at TIMESTAMPTZ;

-- Partial index for the nightly decay sweep — only non-potentiated rows decay.
CREATE INDEX IF NOT EXISTS idx_contact_facts_decay_candidates
    ON contact_facts (org_id, last_coactivated_at)
    WHERE is_potentiated = FALSE AND lifecycle_state = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_contact_facts_potentiated
    ON contact_facts (org_id, contact_id)
    WHERE is_potentiated = TRUE;

-- ── 3. Trigram GIN on interactions.raw_body ─────────────────────────────────
-- Complements search_tsv (mig 063) for substring + ILIKE patterns the tsvector
-- engine doesn't accelerate (e.g. partial-string fuzzy retrieval).

CREATE INDEX IF NOT EXISTS idx_interactions_body_trgm
    ON interactions USING GIN (raw_body gin_trgm_ops);

-- Done. (psql \echo removed — Supabase SQL editor rejects meta-commands.)

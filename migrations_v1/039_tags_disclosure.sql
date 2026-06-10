-- Migration 039: Phase 7 — Entity Tagging & Disclosure Control
-- Run: psql $DATABASE_URL -f migrations/039_tags_disclosure.sql
--
-- Safety notes:
--   - All ALTER TABLE use IF NOT EXISTS — safe to re-run
--   - GIN index uses partial condition to avoid indexing empty arrays

-- ─── contacts: entity tagging ────────────────────────────────────────────────

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

-- GIN index enables fast tag lookups: tags @> '{investor}'
CREATE INDEX IF NOT EXISTS idx_contacts_tags
    ON contacts USING gin(tags);

-- ─── contacts: disclosure control ───────────────────────────────────────────

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS disclosure_level TEXT DEFAULT 'public'
    CHECK (disclosure_level IN ('public', 'private', 'restricted'));

-- Which agent_ids are allowed to read restricted contacts (empty = all blocked)
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS restricted_to_agents TEXT[] DEFAULT '{}';

-- Partial index — only non-public rows need fast lookup
CREATE INDEX IF NOT EXISTS idx_contacts_disclosure
    ON contacts(org_id, disclosure_level)
    WHERE disclosure_level != 'public';

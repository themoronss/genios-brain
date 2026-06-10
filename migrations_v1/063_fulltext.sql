-- Migration 063: Postgres full-text search column on interactions.
--
-- Adds a GENERATED tsvector column so BM25-style retrieval works without
-- maintaining a separate index or duplicating content. GIN index makes
-- prefix/phrase queries fast on the current interactions row count.
--
-- The column is populated on insert/update automatically — no backfill needed
-- for new rows. For existing rows, Postgres re-generates the value on first
-- access to any row; you can force it with: UPDATE interactions SET body=body.

ALTER TABLE interactions
    ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(subject, '')),     'A') ||
        setweight(to_tsvector('english', coalesce(summary, '')),     'B') ||
        setweight(to_tsvector('english', coalesce(raw_snippet, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(raw_body, '')),    'D')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_interactions_tsv
    ON interactions USING GIN (search_tsv);

-- 046: Add segment_id directly on contacts for fast segment-scoped queries.
-- Architecture: segment is written at ingest time via auto-classification.
-- Subscription only gates the query filter — upgrade = instant reveal.

ALTER TABLE contacts
  ADD COLUMN IF NOT EXISTS segment_id UUID REFERENCES graph_segments(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS segment_source TEXT DEFAULT 'auto'
    CHECK (segment_source IN ('auto', 'manual'));

-- Index for segment-scoped context queries (the hot path)
CREATE INDEX IF NOT EXISTS idx_contacts_segment_id
  ON contacts (org_id, segment_id) WHERE segment_id IS NOT NULL;

COMMENT ON COLUMN contacts.segment_id IS 'FK to graph_segments. Written at ingest by auto-classifier, overridable manually.';
COMMENT ON COLUMN contacts.segment_source IS 'auto = classified at ingest, manual = user override via API/UI.';

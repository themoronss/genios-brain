-- Phase 4: Graph Segments (Dept Clusters)
-- Creates named segment (cluster) management tables per PDF spec.

-- Named dept clusters with type classification
CREATE TABLE IF NOT EXISTS graph_segments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    cluster_type TEXT NOT NULL CHECK (cluster_type IN ('Investor','Customer','Team','Vendor','Admin','Other')),
    config      JSONB DEFAULT '{}',
    -- sync config per segment: null = manual, 6/12/18/24 for cron
    sync_interval_hours INTEGER DEFAULT NULL,
    last_synced_at      TIMESTAMPTZ DEFAULT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Members of each segment (contacts assigned to a segment)
CREATE TABLE IF NOT EXISTS segment_members (
    segment_id  UUID NOT NULL REFERENCES graph_segments(id) ON DELETE CASCADE,
    contact_id  UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    added_by    TEXT DEFAULT NULL,
    PRIMARY KEY (segment_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_graph_segments_org_id ON graph_segments(org_id);
CREATE INDEX IF NOT EXISTS idx_segment_members_segment_id ON segment_members(segment_id);
CREATE INDEX IF NOT EXISTS idx_segment_members_contact_id ON segment_members(contact_id);

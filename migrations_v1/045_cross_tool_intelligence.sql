-- Migration 045: Cross-tool intelligence layer
-- Co-attendance edges, initiator tracking, graph intelligence dimensions

-- Co-attendance table (attendee-to-attendee edges for community clustering)
CREATE TABLE IF NOT EXISTS co_attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    contact_a_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    contact_b_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    calendar_event_id UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    event_title TEXT,
    event_at TIMESTAMPTZ,
    co_attendance_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (contact_a_id, contact_b_id, calendar_event_id)
);

CREATE INDEX IF NOT EXISTS idx_co_attendance_org ON co_attendance(org_id);
CREATE INDEX IF NOT EXISTS idx_co_attendance_contact_a ON co_attendance(contact_a_id);
CREATE INDEX IF NOT EXISTS idx_co_attendance_contact_b ON co_attendance(contact_b_id);

-- Initiator email on interactions (who started the thread)
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS initiator_email TEXT;

-- Graph intelligence dimensions (per-org nightly summary)
CREATE TABLE IF NOT EXISTS graph_intelligence_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    relationship_pct FLOAT DEFAULT 0,
    authority_pct FLOAT DEFAULT 0,
    state_pct FLOAT DEFAULT 0,
    precedent_pct FLOAT DEFAULT 0,
    connected_tools TEXT[] DEFAULT '{}',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (org_id)
);

CREATE INDEX IF NOT EXISTS idx_graph_intelligence_org ON graph_intelligence_dimensions(org_id);

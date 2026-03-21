-- Migration 011: MVP V1 Detailing Upgrade
-- Author: GeniOS Team
-- Version: 3.0
-- Date: 2026-03-21
-- Description: New tables (contact_facts, agent_sessions, outcome_events, communities, activity_log)
--              + field additions to contacts, interactions, orgs per MVP V1 Detailing spec

-- ================================================================
-- 1. contact_facts — Individual facts with lifecycle & 5-score system
-- ================================================================

CREATE TABLE IF NOT EXISTS contact_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,

    -- Fact identity
    fact_type TEXT NOT NULL,        -- role, commitment, preference, communication_style, topic, relationship, sentiment_pattern
    fact_value TEXT NOT NULL,       -- The actual fact content
    source TEXT NOT NULL DEFAULT 'gmail',  -- gmail, calendar, manual, inferred

    -- Lifecycle state
    lifecycle_state TEXT NOT NULL DEFAULT 'EXTRACTED'
        CHECK (lifecycle_state IN ('EXTRACTED', 'VALIDATED', 'ACTIVE', 'STALE', 'SUPERSEDED', 'ARCHIVED', 'DELETED')),

    -- 5-score system
    freshness_score FLOAT DEFAULT 1.0,
    confidence_score FLOAT DEFAULT 0.5,
    consistency_score FLOAT DEFAULT 0.5,
    signal_score FLOAT DEFAULT 0.5,
    authority_score FLOAT DEFAULT 0.5,
    composite_score FLOAT DEFAULT 0.5,

    -- Traceability
    source_interaction_id UUID REFERENCES interactions(id) ON DELETE SET NULL,
    superseded_by UUID REFERENCES contact_facts(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contact_facts_org ON contact_facts(org_id);
CREATE INDEX IF NOT EXISTS idx_contact_facts_contact ON contact_facts(contact_id);
CREATE INDEX IF NOT EXISTS idx_contact_facts_lifecycle ON contact_facts(org_id, lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_contact_facts_composite ON contact_facts(composite_score DESC) WHERE lifecycle_state = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_contact_facts_type ON contact_facts(org_id, contact_id, fact_type);

-- ================================================================
-- 2. agent_sessions — Multi-agent coordination
-- ================================================================

CREATE TABLE IF NOT EXISTS agent_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'COMPLETED', 'FAILED')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    UNIQUE(org_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_org ON agent_sessions(org_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_agent ON agent_sessions(org_id, agent_id);

-- ================================================================
-- 3. outcome_events — Feedback loop from agent executions
-- ================================================================

CREATE TABLE IF NOT EXISTS outcome_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    session_id TEXT,
    agent_id TEXT,
    action_type TEXT NOT NULL,       -- email_sent, meeting_scheduled, crm_updated, etc.
    target_entity TEXT,              -- Contact name or email
    outcome_type TEXT NOT NULL       -- EXECUTED, EDITED, REJECTED, ESCALATED
        CHECK (outcome_type IN ('EXECUTED', 'EDITED', 'REJECTED', 'ESCALATED')),
    interaction_record JSONB,        -- {subject, direction, topics[], commitment_made}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outcome_events_org ON outcome_events(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outcome_events_session ON outcome_events(org_id, session_id);

-- ================================================================
-- 4. communities — Louvain cluster assignments
-- ================================================================

CREATE TABLE IF NOT EXISTS communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    community_id INT NOT NULL,
    color TEXT NOT NULL DEFAULT '#6366f1',
    node_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(org_id, community_id)
);

CREATE INDEX IF NOT EXISTS idx_communities_org ON communities(org_id);

-- ================================================================
-- 5. activity_log — System activity feed
-- ================================================================

CREATE TABLE IF NOT EXISTS activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,        -- email_detected, contact_created, relationship_updated, graph_synced, sync_started, sync_completed, sync_failed
    event_data JSONB DEFAULT '{}',   -- {contact_name, old_stage, new_stage, email_subject, ...}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_org ON activity_log(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_type ON activity_log(org_id, event_type);

-- ================================================================
-- 6. Field additions to contacts table
-- ================================================================

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS community_id INT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS size_score FLOAT DEFAULT 0.5;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS consistency_score FLOAT DEFAULT 0.5;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS authority_score FLOAT DEFAULT 0.5;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS composite_score FLOAT DEFAULT 0.5;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS response_rate FLOAT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS avg_response_time_hours FLOAT;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_bidirectional BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_contacts_community ON contacts(org_id, community_id);
CREATE INDEX IF NOT EXISTS idx_contacts_composite ON contacts(org_id, composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_size ON contacts(org_id, size_score DESC);

-- ================================================================
-- 7. Field additions to interactions table
-- ================================================================

ALTER TABLE interactions ADD COLUMN IF NOT EXISTS is_bidirectional BOOLEAN DEFAULT FALSE;

-- ================================================================
-- 8. Field additions to orgs table
-- ================================================================

ALTER TABLE orgs ADD COLUMN IF NOT EXISTS sync_interval_hours INT DEFAULT 24;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS graph_quality_score FLOAT DEFAULT 0.0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS aer FLOAT DEFAULT 0.0;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS brain_status TEXT DEFAULT 'building';

-- ================================================================
-- 9. Add SOFT status to commitments if not already present
-- ================================================================

ALTER TABLE commitments DROP CONSTRAINT IF EXISTS commitments_status_check;
ALTER TABLE commitments ADD CONSTRAINT commitments_status_check
    CHECK (status IN ('OPEN', 'FULFILLED', 'OVERDUE', 'MISSED', 'SOFT'));

-- ================================================================
-- 10. Add NEEDS_ATTENTION to relationship stage support
-- ================================================================
-- No constraint exists on relationship_stage (it's a TEXT field), so this is just documentation.
-- Valid stages: ACTIVE, WARM, NEEDS_ATTENTION, DORMANT, COLD, AT_RISK

-- ================================================================
-- Done
-- ================================================================

\echo '✅ Migration 011: MVP V1 Detailing upgrade completed'
\echo '   - contact_facts table (lifecycle + 5-score system)'
\echo '   - agent_sessions table (multi-agent coordination)'
\echo '   - outcome_events table (feedback loop)'
\echo '   - communities table (Louvain clustering)'
\echo '   - activity_log table (system activity feed)'
\echo '   - contacts: community_id, size_score, consistency, authority, composite, response metrics, bidirectionality'
\echo '   - interactions: is_bidirectional'
\echo '   - orgs: sync_interval_hours, graph_quality_score, aer, brain_status'

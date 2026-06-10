-- Migration: Add enhanced graph fields for confidence, sentiment evolution, and commitment tracking
-- Date: 2026-03-13
-- Purpose: Enable rich context bundle generation with EWMA, trends, and commitment lifecycle

-- 1. Enhance contacts table with new scoring fields
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.5;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS sentiment_ewma FLOAT DEFAULT 0.0;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS sentiment_trend TEXT DEFAULT 'STABLE' CHECK (sentiment_trend IN ('IMPROVING', 'STABLE', 'DECLINING'));

-- 2. Update metadata JSONB to include source tracking
-- Structure: {"sources": ["gmail"], "source_weights": {"gmail": 0.35}, "last_recalc_at": "2026-03-13T10:00:00Z", "entity_resolution_confidence": 0.95}
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS sources TEXT[] DEFAULT '{"gmail"}';

-- 3. Enhance interactions table with interaction type and engagement signals
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS interaction_type TEXT DEFAULT 'email' CHECK (interaction_type IN ('email_reply', 'email_one_way', 'commitment', 'meeting', 'other'));
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS reply_time_hours INT;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS weight_score FLOAT DEFAULT 0.0;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS topics TEXT[] DEFAULT '{}';

-- 4. Create commitments table for lifecycle tracking
CREATE TABLE IF NOT EXISTS commitments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    commit_text TEXT NOT NULL,
    owner TEXT NOT NULL CHECK (owner IN ('them', 'us')),
    due_date TIMESTAMPTZ,
    status TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'FULFILLED', 'OVERDUE', 'MISSED')),
    source_interaction_id UUID REFERENCES interactions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    UNIQUE(org_id, contact_id, commit_text, created_at)
);

-- 5. Add sentiment history tracking to metadata
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS sentiment_history JSONB DEFAULT '[]'::jsonb;
-- Structure: [{"timestamp": "2026-03-13T10:00:00Z", "sentiment": 0.6, "source": "email"}, ...]

-- 6. Add communication style tracking
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS communication_style JSONB DEFAULT '{}'::jsonb;
-- Structure: {"preferred_channel": "email", "avg_response_hours": 24, "prefers_short": true, "formality": "semi-formal"}

-- 7. Add topics with recency weighting
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS topics_weighted JSONB DEFAULT '[]'::jsonb;
-- Structure: [{"topic": "Series A", "weight": 0.95, "last_mentioned": "2026-03-10", "count": 5}, ...]

-- 8. Indexes for performance on Gmail-focused queries
CREATE INDEX IF NOT EXISTS idx_contacts_confidence ON contacts(org_id, confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_stage_recency ON contacts(org_id, relationship_stage, last_interaction_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(org_id, interaction_type);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(org_id, status, due_date);
CREATE INDEX IF NOT EXISTS idx_commitments_contact ON commitments(org_id, contact_id, status);

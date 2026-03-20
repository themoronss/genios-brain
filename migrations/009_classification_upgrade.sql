-- Migration 009: Email Classification & Signal Scoring Upgrade
-- Author: GeniOS Team
-- Version: 1.1
-- Date: 2026-03-18
-- Description: Add email classification, signal scoring, freshness decay, and state events

-- ================================================================
-- 1. Create state_events table for SYSTEM emails (GST, payments, invoices)
-- ================================================================

CREATE TABLE IF NOT EXISTS state_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    type TEXT NOT NULL,  -- GST, PAYMENT, INVOICE, ORDER, SHIPPING, OTHER
    status TEXT,         -- FILED, PENDING, CONFIRMED, RECEIVED, IN_TRANSIT, UNKNOWN
    metadata JSONB,      -- Flexible storage for email details (subject, sender, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- Index for fast querying by organization and type
CREATE INDEX IF NOT EXISTS idx_state_events_org_type ON state_events(org_id, type);
CREATE INDEX IF NOT EXISTS idx_state_events_created_at ON state_events(created_at DESC);

-- ================================================================
-- 2. Add signal_score to interactions table
-- ================================================================

-- Signal score: 0.0-1.0 computed from intent + engagement + length + commitments
-- Replaces weight_score as primary sorting metric (weight_score kept for backward compatibility)
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS signal_score FLOAT;

-- Create index for efficient sorting
CREATE INDEX IF NOT EXISTS idx_interactions_signal_score ON interactions(signal_score DESC NULLS LAST);

-- ================================================================
-- 3. Add freshness_score to contacts table
-- ================================================================

-- Freshness score: 0.1-1.0 decay based on days_since_last and relationship_stage
-- Uses halflife: ACTIVE=7d, WARM=30d, DORMANT=60d, COLD=90d
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS freshness_score FLOAT DEFAULT 1.0;

-- Create index for efficient sorting
CREATE INDEX IF NOT EXISTS idx_contacts_freshness_score ON contacts(freshness_score DESC);

-- ================================================================
-- 4. Add source field to interactions (multi-tool support)
-- ================================================================

-- Source: 'gmail', 'calendar', 'docs', 'slack' (future-ready)
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'gmail';

-- Create index for filtering by source
CREATE INDEX IF NOT EXISTS idx_interactions_source ON interactions(source);

-- ================================================================
-- 5. Create composite index for optimized context bundle queries
-- ================================================================

-- Optimize: ORDER BY signal_score DESC, freshness_score DESC, weight_score DESC
CREATE INDEX IF NOT EXISTS idx_interactions_context_sorting 
ON interactions(contact_id, signal_score DESC NULLS LAST, interaction_at DESC);

-- ================================================================
-- Migration Complete
-- ================================================================

-- Verification query to confirm changes
DO $$
BEGIN
    RAISE NOTICE 'Migration 009 applied successfully';
    RAISE NOTICE 'Added: state_events table';
    RAISE NOTICE 'Added: interactions.signal_score';
    RAISE NOTICE 'Added: contacts.freshness_score';
    RAISE NOTICE 'Added: interactions.source';
END $$;

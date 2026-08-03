-- Migration 010: State Graph Upgrade - Structured State Entities
-- Author: GeniOS Team
-- Version: 2.2
-- Date: 2026-03-18
-- Description: Upgrade from append-only state_events to structured state_entities with UPSERT logic

-- ================================================================
-- 1. Create structured state_entities table (replacing state_events)
-- ================================================================

CREATE TABLE IF NOT EXISTS state_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL,
    
    -- Entity Identity (ensures same real-world event = same record)
    entity_type TEXT NOT NULL,  -- GST | PAYMENT | INVOICE | ORDER | COMPLIANCE
    entity_id TEXT NOT NULL,    -- Unique identifier per org (GST_Q2_2025, PAYMENT_UTR_123, etc)
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | FILED | CONFIRMED | OVERDUE | HISTORICAL
    
    -- Structured fields (not just metadata JSON)
    amount NUMERIC,                          -- For payments, invoices
    vendor TEXT,                             -- For payments, invoices
    reference_id TEXT,                       -- ARN (GST), UTR (Payment), invoice_number, order_id, tracking_id
    due_date TIMESTAMP,                      -- When is it due?
    event_date TIMESTAMP,                    -- When did it happen?
    
    -- Traceability
    source_email_id TEXT,                    -- Email message ID that created/updated this
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Flexible storage for additional data
    metadata JSONB,
    
    -- Constraints
    UNIQUE(org_id, entity_id)  -- Ensure same entity_id = same record per org
);

-- ================================================================
-- 2. Indexes for query performance
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_state_entities_org_type 
    ON state_entities(org_id, entity_type);

CREATE INDEX IF NOT EXISTS idx_state_entities_org_status 
    ON state_entities(org_id, status);

CREATE INDEX IF NOT EXISTS idx_state_entities_due_date 
    ON state_entities(due_date) WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_state_entities_entity_id 
    ON state_entities(org_id, entity_id);

CREATE INDEX IF NOT EXISTS idx_state_entities_updated_at 
    ON state_entities(org_id, updated_at DESC);

-- ================================================================
-- 3. Print success message
-- ================================================================

\echo '✅ Migration 010: State Graph upgrade completed successfully'
\echo '   - state_entities table created'
\echo '   - Unique constraint on (org_id, entity_id)'
\echo '   - 5 performance indexes created'

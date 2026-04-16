-- Phase 1.1: Support async LLM extraction
-- Sync writes raw interaction rows instantly; Celery worker extracts in batch.

-- Store the raw email body so the async extractor can re-process without
-- hitting the Gmail API again.
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS raw_body TEXT;

-- Track extraction status: 'pending' | 'extracted' | 'failed' | 'skipped'
-- NULL = legacy rows (already extracted inline during sync).
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS extraction_status TEXT;

-- Index for the worker to find pending rows efficiently.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interactions_extraction_pending
    ON interactions (org_id, extraction_status)
    WHERE extraction_status = 'pending';

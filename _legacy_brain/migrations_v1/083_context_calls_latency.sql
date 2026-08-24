-- Migration 083 — latency + cache-path tracking on context_calls
-- Date: 2026-05-02
-- Purpose: Power /v1/benchmarks/scorecard p95/p99 latency + per-path breakdown.
-- Both columns are nullable so old rows are unaffected.

ALTER TABLE context_calls
    ADD COLUMN IF NOT EXISTS latency_ms  INT,
    ADD COLUMN IF NOT EXISTS cache_source TEXT;  -- 'precomputed' | 'redis' | 'minimal' | 'fresh'

-- p95/p99 over 30d windows: latency-only filter
CREATE INDEX IF NOT EXISTS idx_context_calls_latency_time
    ON context_calls(called_at DESC)
    WHERE latency_ms IS NOT NULL;

-- Migration 023: Sync Stats Tracking
-- Adds per-sync counters to calendar_sync_state so the dashboard can show
-- "what data was synced / what was filtered" after each calendar sync run.
-- Run: psql $DATABASE_URL -f migrations/023_sync_stats.sql

ALTER TABLE calendar_sync_state
  ADD COLUMN IF NOT EXISTS last_sync_events_added   INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_sync_events_filtered INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_events_synced       INTEGER DEFAULT 0;

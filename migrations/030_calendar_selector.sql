-- Migration 030: Calendar selector support
-- Adds sync_enabled + calendar_name to calendar_sync_state
-- so users can choose which calendars to sync.

ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS sync_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS calendar_name TEXT;

-- prep_context_at was referenced in code but missing from schema
ALTER TABLE upcoming_meetings ADD COLUMN IF NOT EXISTS prep_context_at TIMESTAMPTZ;

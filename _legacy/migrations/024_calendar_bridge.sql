-- Migration 024: Calendar Bridge — idempotent interaction index
-- Allows calendar_bridge.py to safely re-run without duplicate interactions.
-- Run: psql $DATABASE_URL -f migrations/024_calendar_bridge.sql

-- One interaction per contact per calendar event
CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_calendar_contact
  ON interactions(calendar_event_id, contact_id)
  WHERE calendar_event_id IS NOT NULL;

-- Migration 007: CC/many-to-many interaction constraint
-- Date: 2026-03-17
-- Purpose: Allow multiple contact rows per gmail_message_id (one per CC participant)
--           so the graph captures many-to-many email relationships.
--
-- BEFORE: UNIQUE(gmail_message_id)       → only one contact per email
-- AFTER:  UNIQUE(gmail_message_id, contact_id) → one row per participant per email

-- Step 1: Drop the old single-column unique constraint
ALTER TABLE interactions
    DROP CONSTRAINT IF EXISTS interactions_gmail_message_id_key;

-- Step 2: Add the new composite unique constraint
ALTER TABLE interactions
    ADD CONSTRAINT interactions_gmail_message_id_contact_id_key
    UNIQUE (gmail_message_id, contact_id);

-- Step 3: Update interaction_type check constraint to allow 'cc' direction
-- (direction field, not type — but we add 'cc' as a valid direction value)
-- The direction column has no existing CHECK constraint so no changes needed.

-- Add index to support queries that look up all participants of an email thread
CREATE INDEX IF NOT EXISTS idx_interactions_gmail_message
    ON interactions(gmail_message_id);

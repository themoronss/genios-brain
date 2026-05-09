-- Migration 092: connection / sync status tracking on connector_credentials.
--
-- Phase 12 polish: dashboard needs Gmail-grade visibility on every connector
-- account — connect-time validation, every sync run's outcome, last error,
-- stale detection. Without these columns, the customer can't tell from the UI
-- whether their Inkbox/IMAP credentials still work.
--
-- Additive only. Idempotent.

BEGIN;

ALTER TABLE connector_credentials
    ADD COLUMN IF NOT EXISTS last_sync_status      TEXT,
    -- 'success' | 'auth_failed' | 'failed' | 'never_synced' | 'syncing' | 'unreachable'
    ADD COLUMN IF NOT EXISTS last_sync_error       TEXT,
    -- Up to 500 chars of the last error message (e.g. "401 Unauthorized")
    ADD COLUMN IF NOT EXISTS last_sync_at          TIMESTAMPTZ,
    -- Distinct from last_event_at (which only updates on accepted ingest);
    -- this updates on EVERY sync attempt, success or fail.
    ADD COLUMN IF NOT EXISTS consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_email_count      INTEGER;
    -- emails ingested in the most recent sync (display: "47 emails")

CREATE INDEX IF NOT EXISTS idx_conn_creds_status
    ON connector_credentials(org_id, last_sync_status)
    WHERE is_active = TRUE;

COMMIT;

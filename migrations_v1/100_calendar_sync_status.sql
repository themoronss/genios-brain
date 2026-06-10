-- Add sync_status tracking to calendar_sync_state.
--
-- Bug: integrations_auth.get_integrations_status queries
-- `COALESCE(sync_status, 'idle')` on calendar_sync_state, but this column
-- was never added (Gmail got it in mig 044 on oauth_tokens; Google Calendar
-- was missed). Page load on /dashboard/integrations crashed with
-- "column sync_status does not exist" and poisoned the SQLAlchemy
-- session for the rest of the request.

ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS sync_status     VARCHAR(20) DEFAULT 'idle';
ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS sync_total      INTEGER     DEFAULT 0;
ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS sync_processed  INTEGER     DEFAULT 0;
ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS sync_error      TEXT;
ALTER TABLE calendar_sync_state ADD COLUMN IF NOT EXISTS sync_started_at TIMESTAMP WITH TIME ZONE;

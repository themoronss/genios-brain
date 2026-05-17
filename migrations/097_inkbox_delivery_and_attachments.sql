-- 097_inkbox_delivery_and_attachments.sql
--
-- Inkbox push mode: we now receive `message.sent`, `message.delivered`,
-- `message.bounced`, `message.failed`, `message.forwarded` webhook events in
-- addition to `message.received`. Outbound interactions need a place to track
-- delivery lifecycle. SMS/MMS attachments also need preservation.
--
-- delivery_state JSONB shape:
--   {
--     "status": "sent" | "delivered" | "bounced" | "failed" | "forwarded",
--     "sent_at": iso, "delivered_at": iso, "bounced_at": iso, "failed_at": iso,
--     "bounce_reason": "...", "failure_reason": "...",
--     "forwarded_to": ["addr"], "forwarded_at": iso
--   }
--
-- attachments JSONB shape (for MMS / future email):
--   [{"url": "https://...", "content_type": "image/jpeg", "filename": "..."}]

ALTER TABLE interactions ADD COLUMN IF NOT EXISTS delivery_state JSONB DEFAULT '{}'::jsonb;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS attachments    JSONB DEFAULT '[]'::jsonb;

-- Quick lookup of bounced messages for retention / cleanup jobs.
CREATE INDEX IF NOT EXISTS idx_interactions_delivery_status
    ON interactions ((delivery_state->>'status'))
    WHERE delivery_state ? 'status';

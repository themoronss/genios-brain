-- Add sync progress tracking columns to oauth_tokens
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'idle';
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS sync_total INTEGER DEFAULT 0;
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS sync_processed INTEGER DEFAULT 0;
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS sync_error TEXT;
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS sync_started_at TIMESTAMP WITH TIME ZONE;

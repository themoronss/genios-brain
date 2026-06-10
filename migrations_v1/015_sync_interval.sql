-- Add configurable sync interval per org (default 24 hours)
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS sync_interval_hours INTEGER DEFAULT 24;

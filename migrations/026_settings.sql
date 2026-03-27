-- Migration 026: Settings support — profile fields, notification prefs
-- Run: psql $DATABASE_URL -f migrations/026_settings.sql

-- Profile fields
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS company TEXT;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS first_name TEXT;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS last_name TEXT;

-- Notification preferences (JSONB for flexibility)
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS notification_prefs JSONB DEFAULT '{}';

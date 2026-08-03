-- Add contact_role column to interactions (used by role_drift detector)
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS contact_role TEXT;
CREATE INDEX IF NOT EXISTS idx_interactions_contact_role ON interactions(org_id, contact_role) WHERE contact_role IS NOT NULL;

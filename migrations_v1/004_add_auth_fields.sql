-- Add email and password authentication to orgs table

ALTER TABLE orgs
ADD COLUMN email TEXT UNIQUE,
ADD COLUMN password_hash TEXT;

-- Backfill existing orgs with placeholder data
UPDATE orgs 
SET email = CONCAT('user_', id::text, '@genios.local')
WHERE email IS NULL;

UPDATE orgs
SET password_hash = '$2b$12$placeholder'
WHERE password_hash IS NULL;

-- Add index for faster email lookups
CREATE INDEX idx_orgs_email ON orgs(email);

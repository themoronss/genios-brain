-- Migration 032: Hash API keys at rest using SHA-256 via pgcrypto
-- This replaces plain-text api_key storage.
-- deps.py already handles dual lookup (raw + hashed) for backward compat.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Store hashed API key in a new column, then swap
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS api_key_hash TEXT;

-- Hash all existing plain-text keys
UPDATE orgs
SET api_key_hash = encode(digest(api_key, 'sha256'), 'hex')
WHERE api_key IS NOT NULL AND api_key_hash IS NULL;

-- Index for fast hash lookup
CREATE UNIQUE INDEX IF NOT EXISTS idx_orgs_api_key_hash
    ON orgs(api_key_hash)
    WHERE api_key_hash IS NOT NULL;

-- NOTE: We keep the api_key column for now (backward compat with existing
-- dashboard sessions). After all clients rotate their keys, run:
--   ALTER TABLE orgs DROP COLUMN api_key;
-- and rename api_key_hash → api_key.
-- The app's deps.py will do a dual-column lookup until that migration runs.

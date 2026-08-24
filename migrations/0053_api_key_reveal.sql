-- Re-viewable org /v1 API keys (same as agent keys, migration 0052, but for api_keys). Lets the
-- Settings → API keys panel reveal/copy a key again instead of only showing the prefix. Raw key
-- is stored encrypted at rest with GENIOS_CRYPTO_KEY (Fernet); the hash still does auth. Owner-gated.

alter table api_keys add column if not exists key_enc bytea;

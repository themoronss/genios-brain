-- Re-viewable agent API keys. The product wants the owner to be able to copy/see an agent's key
-- again at any time (not only once at creation). We can't recover a key from key_hash (one-way),
-- so we ALSO store the raw key encrypted at rest with GENIOS_CRYPTO_KEY (Fernet) in key_enc, and
-- a reveal endpoint decrypts it for the owner. Hash stays for auth; key_enc is only for display.
-- Trade-off: a retrievable secret is weaker than hash-only, but it's owner-gated and encrypted.

alter table agent_registry add column if not exists key_enc bytea;

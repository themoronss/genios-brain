-- 0013 — workspace (non-Google) custom integration accounts.
-- Google (Gmail/Calendar) stays on Composio. This holds the "bring your own" mail sources a
-- customer connects at workspace level: a hosted inbox (API key: email+SMS+voice) and self-hosted
-- IMAP. Credentials (api_key / imap password) are Fernet-encrypted at rest — never plaintext.
create table if not exists workspace_accounts (
    account_id            text primary key,
    org_id                text not null,
    tool                  text not null,             -- 'inkbox' (hosted inbox) | 'imap'
    channel               text not null default 'email',
    label                 text not null,
    enc_credentials       bytea not null,            -- Fernet(json(credentials))
    sync_status           text not null default 'never_synced',
    sync_error            text,
    last_sync_at          timestamptz,
    last_event_at         timestamptz,
    consecutive_failures  integer not null default 0,
    is_active             boolean not null default true,
    created_at            timestamptz not null default now()
);

create index if not exists ix_workspace_accounts_org
    on workspace_accounts (org_id) where is_active;

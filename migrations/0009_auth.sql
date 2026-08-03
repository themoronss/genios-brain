-- GeniOS Engine · Auth & identity (ported from genios-brain 001/034/086, engine-native).
-- Two credential families, both resolving to an org_id server-side (never from a query param):
--   • JWT dashboard session (issued by /auth/login) — stateless.
--   • gn_live_… API key — SHA-256 hashed at rest, Redis-cached, carries a scope grant.
-- org_id is TEXT here to match the engine's existing tables (source_events.org_id etc.).

-- Tenants. api_key_hash = the org's primary/legacy key; per-key rows live in api_keys.
create table if not exists orgs (
    id                text primary key,                 -- 'org_…' (engine-native text id)
    name              text not null,
    email             text unique,                      -- login identity (nullable for API-only orgs)
    pass_hash         text,                             -- pbkdf2$iterations$salt$hash (stdlib)
    api_key_hash      text,                             -- sha256 of the org's primary gn_live_ key
    subscription_tier text not null default 'trial',    -- trial | startup | …
    plan_status       text not null default 'active',   -- active | suspended | invalid
    created_at        timestamptz not null default now()
);
create index if not exists orgs_by_email on orgs (lower(email));
create index if not exists orgs_by_apikey on orgs (api_key_hash);

-- Minted keys. A tenant mints multiple gn_live_ keys, each scoped (scopes[]) and bound to an
-- agent slug. verify() checks scope membership; last_used_at powers usage/metering.
create table if not exists api_keys (
    id           text primary key,                      -- 'key_…'
    org_id       text not null references orgs(id) on delete cascade,
    key_hash     text not null unique,                  -- sha256(gn_live_…)
    key_prefix   text not null,                         -- 'gn_live_ab12' — shown in UI, safe
    name         text,
    agent_id     text,                                  -- slug this key acts as (nullable)
    scopes       text[] not null default '{}',          -- AGENT_API_SCOPES ∪ AGENT_ACTIONS
    is_active    boolean not null default true,
    created_at   timestamptz not null default now(),
    last_used_at timestamptz
);
create index if not exists api_keys_by_org on api_keys (org_id);

-- L7 kill-switch + feature flags (Redis-cached, checked per request, fail-open).
create table if not exists feature_flags (
    key        text primary key,
    enabled    boolean not null default true,
    updated_at timestamptz not null default now()
);
insert into feature_flags (key, enabled) values ('kill_switch_all', true)
    on conflict (key) do nothing;

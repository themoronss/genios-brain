-- Dashboard Agent Registry metadata. The runtime auth table (agent_registry: key_hash,
-- allowed_actions) predates the dashboard's richer model; these nullable columns add the
-- management surface (name/status/scope/key display) without touching runtime verify().
alter table agent_registry add column if not exists name             text;
alter table agent_registry add column if not exists description      text;
alter table agent_registry add column if not exists status           text not null default 'active';
alter table agent_registry add column if not exists scope            jsonb not null default '{}';
alter table agent_registry add column if not exists scope_version    int  not null default 1;
alter table agent_registry add column if not exists scope_updated_at timestamptz;
alter table agent_registry add column if not exists is_default       boolean not null default false;
alter table agent_registry add column if not exists key_prefix       text;
alter table agent_registry add column if not exists key_last_used_at timestamptz;

-- One row per (org_id, agent_id) — assumed by every read/write path but never enforced (0002 gave
-- only a PK on id). Dedupe any pre-existing collisions (keep one), then enforce it. Enables the
-- register() UPSERT and closes the create-agent TOCTOU race.
delete from agent_registry a using agent_registry b
    where a.org_id = b.org_id and a.agent_id = b.agent_id and a.ctid < b.ctid;
create unique index if not exists agent_registry_org_agent on agent_registry (org_id, agent_id);

-- Per-agent account access grants (which connected mailboxes/calendars an agent may read).
create table if not exists agent_grants (
    grant_id     text primary key,
    org_id       text not null,
    agent_id     text not null,
    account_id   text not null,
    account_kind text not null,        -- 'oauth' | 'connector'
    tool         text,
    label        text,
    granted_at   timestamptz not null default now(),
    unique (org_id, agent_id, account_id)
);
create index if not exists agent_grants_by_agent on agent_grants (org_id, agent_id);

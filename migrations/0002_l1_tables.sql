-- GeniOS Engine · L1 · remaining capture tables. org_id on every row.

-- One connected source per ORG (tenant). 30 startups = 30 rows. Per-org identity
-- (composio_user_id) lives HERE, never in .env. The Composio API key is global.
create table if not exists connections (
    connection_id       text primary key,
    org_id              text not null,
    provider            text not null default 'google',
    source_type         text not null default 'gmail',
    composio_user_id    text,                   -- this org's Gmail label in Composio
    ownership_type      text not null default 'workspace',
    external_account_id text,
    granted_scopes      text[] not null default '{}',
    status              text not null default 'connected',
    encrypted_secret_ref text,
    capture_scope       jsonb not null default '{}',
    expires_at          timestamptz,
    created_at          timestamptz not null default now()
);
create index if not exists connections_by_org on connections (org_id, status);

-- (capture scopes live as connections.capture_scope jsonb — no separate table)

create table if not exists document_jobs (
    id               text primary key,
    org_id           text not null,
    event_id         text not null,
    format           text,
    native_parse_used boolean not null default false,
    ocr_engine       text,
    ocr_pages        int not null default 0,
    avg_confidence   numeric(4,3),
    status           text not null             -- accepted | ocr_review_required | unsupported
);

-- (gate decisions are captured in event_trace — no separate gate_logs table)

create table if not exists parked_events (
    event_id    text primary key,
    org_id      text not null,
    source      text,
    reason_code text not null,
    stage       text,
    trace       jsonb not null default '[]',
    status      text not null default 'pending',
    created_at  timestamptz not null default now()
);

-- (classifier_runs is L2's LLM replay cache — added in the L2 migration, not L1)

create table if not exists agent_registry (
    id              text primary key,
    org_id          text not null,
    agent_id        text not null,
    key_hash        text not null,
    allowed_actions text[] not null default '{}',
    created_at      timestamptz not null default now()
);

create table if not exists agent_events (
    id              text primary key,
    org_id          text not null,
    agent_id        text not null,
    client_event_id text not null,
    action_taken    text not null,
    target_hint     jsonb not null default '{}',
    result          text,
    occurred_at     timestamptz not null
);
create unique index if not exists agent_events_idem on agent_events (org_id, agent_id, client_event_id);

create table if not exists human_events (
    id          text primary key,
    org_id      text not null,
    type        text not null,
    actor_id    text not null,
    target      jsonb not null default '{}',
    detail      jsonb not null default '{}',
    occurred_at timestamptz not null
);

create table if not exists source_coverage (
    org_id      text not null,
    domain      text not null,
    required    text[] not null default '{}',
    connected   text[] not null default '{}',
    freshness   jsonb not null default '{}',
    coverage_ready boolean not null default false,
    primary key (org_id, domain)
);

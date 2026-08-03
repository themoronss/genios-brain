-- GeniOS Engine · L1 capture · initial tables (Supabase / Postgres)
-- Laws: org_id on every table · raw content encrypted + short TTL · append-only events.

create table if not exists source_events (
    event_id           text primary key,
    org_id             text not null,
    connection_id      text not null,
    source             text not null,
    object_type        text not null,
    source_object_id   text not null,
    parent_object_id   text,
    dedup_key          text not null,
    actor              jsonb not null,
    occurred_at        timestamptz not null,
    captured_at        timestamptz not null default now(),
    sync_mode          text not null default 'incremental',
    payload_ref        text,
    capture_confidence numeric(4,3) not null default 1.0,
    schema_version     int not null default 1
);
create unique index if not exists source_events_dedup
    on source_events (org_id, dedup_key);

create table if not exists raw_payloads (
    id           text primary key,
    org_id       text not null,
    event_id     text not null references source_events (event_id),
    content_type text,
    enc_content  bytea,                       -- encrypted at rest
    expires_at   timestamptz not null         -- short TTL
);

create table if not exists sync_cursors (
    id             text primary key,
    org_id         text not null,
    connection_id  text not null,
    source         text not null,
    cursor         text,
    watermark      timestamptz,
    last_object_id text,
    updated_at     timestamptz not null default now()
);

-- The debug core: every per-event, per-stage decision (pass/drop/park/emit).
create table if not exists event_trace (
    id          bigserial primary key,
    org_id      text not null,
    event_id    text not null,
    dedup_key   text,
    source      text,
    stage       text not null,
    action      text not null,               -- pass | drop | park | emit | short_circuit
    reason_code text,
    detail      jsonb not null default '{}',
    at          timestamptz not null default now()
);
create index if not exists event_trace_by_event on event_trace (org_id, event_id);
create index if not exists event_trace_by_stage on event_trace (org_id, stage, action);

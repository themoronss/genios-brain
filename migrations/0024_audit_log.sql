-- Governance: audit_log (dashboard → Settings → Audit). Append-only trail of who did what — refs +
-- counts only, never content (compliance surface). Written via platform/audit.record() at the
-- highest-signal actions (login, agent create, policy change, upload, data erasure). Ported from
-- genios-brain (core/foundations/audit).
create table if not exists audit_log (
    id             bigint generated always as identity primary key,
    org_id         text not null,
    actor_type     text not null default 'system',       -- user | agent | system
    actor_id       text,
    action         text not null,
    target_type    text,
    target_id      text,
    metadata_jsonb jsonb not null default '{}',
    timestamp      timestamptz not null default now()
);
create index if not exists audit_log_by_org_time   on audit_log (org_id, timestamp desc);
create index if not exists audit_log_by_org_action on audit_log (org_id, action, timestamp desc);

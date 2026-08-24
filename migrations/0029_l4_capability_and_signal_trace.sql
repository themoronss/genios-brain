-- Persist the exact capability bytes that shaped a Layer 4 decision and link every emitted
-- signal to its authoritative reasoning run.  Both relationships are tenant-scoped.

create table if not exists reasoning_capability_snapshots (
    org_id                 text not null references orgs (id) on delete cascade,
    capability_snapshot_id text not null,
    capability_id          text not null,
    capability_version     text not null,
    manifest               jsonb not null,
    manifest_hash          text not null,
    created_at             timestamptz not null default now(),
    primary key (org_id, capability_snapshot_id),
    unique (org_id, capability_id, capability_version),
    check (jsonb_typeof(manifest) = 'object'),
    check (manifest_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists reasoning_capability_by_identity
    on reasoning_capability_snapshots (org_id, capability_id, capability_version);

alter table reasoning_context_snapshots
    add constraint reasoning_context_capability_snapshot_fk
    foreign key (org_id, capability_snapshot_id)
    references reasoning_capability_snapshots (org_id, capability_snapshot_id)
    not valid;

alter table signals add column if not exists reasoning_run_id text;

alter table signals
    add constraint signals_reasoning_run_fk
    foreign key (org_id, reasoning_run_id)
    references reasoning_runs (org_id, run_id)
    not valid;

create index if not exists signals_by_reasoning_run
    on signals (org_id, reasoning_run_id)
    where reasoning_run_id is not null;

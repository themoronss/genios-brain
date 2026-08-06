-- Bind every new signal projection to the exact selected candidate and decision.
-- Historical signals remain version 0 and are intentionally non-authoritative until
-- a fresh Layer 4 sweep replaces them with a fully bound projection.

-- Effective configuration is tenant-owned retention data.  Older migrations made
-- (org_id, snapshot_id) its identity but never attached ownership to orgs, so an
-- account deletion could leave immutable Layer 4 configuration behind.
alter table config_snapshots
    add constraint config_snapshots_org_fk
    foreign key (org_id) references orgs (id) on delete cascade
    not valid;

-- Monotonic tenant-pack authority closes the config read/publication race. Every state, version,
-- LVL2, or LVL3 mutation increments this value; version-1 signals bind the exact observed epoch.
alter table tenant_packs
    add column if not exists authority_revision bigint not null default 1;

alter table tenant_packs
    add constraint tenant_packs_authority_revision_check
    check (authority_revision > 0) not valid;

alter table signals add column if not exists reasoning_candidate_id text;
alter table signals add column if not exists reasoning_decision_hash text;
alter table signals add column if not exists authority_expires_at timestamptz;
alter table signals add column if not exists authority_pack_revision bigint;
alter table signals
    add column if not exists authority_binding_version smallint not null default 0;

alter table reasoning_run_outputs
    add constraint reasoning_outputs_decision_identity
    unique (org_id, run_id, decision_hash);

alter table signals
    add constraint signals_reasoning_candidate_fk
    foreign key (org_id, reasoning_run_id, reasoning_candidate_id)
    references reasoning_candidates (org_id, run_id, candidate_id)
    not valid;

alter table signals
    add constraint signals_reasoning_decision_fk
    foreign key (org_id, reasoning_run_id, reasoning_decision_hash)
    references reasoning_run_outputs (org_id, run_id, decision_hash)
    not valid;

alter table signals
    add constraint signals_authority_binding_shape
    check (
        authority_binding_version = 0
        or (
            authority_binding_version = 1
            and reasoning_run_id is not null
            and reasoning_candidate_id is not null
            and reasoning_decision_hash is not null
            and authority_expires_at is not null
            and authority_pack_revision is not null
            and authority_pack_revision > 0
        )
    ) not valid;

alter table signals
    add constraint signals_authority_binding_version_check
    check (authority_binding_version in (0, 1)) not valid;

create index if not exists signals_authority_expiry
    on signals (org_id, status, authority_expires_at)
    where authority_binding_version = 1;

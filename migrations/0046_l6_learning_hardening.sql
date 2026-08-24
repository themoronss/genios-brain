-- GeniOS Engine · Layer 6 — Learning hardening (= the spec's 0047). Additive.
--
-- 0045 gave Layer 6 its eight ledgers. This adds the three tables the safety story needs:
--
--   learning_event_inbox        trusted structured events/memory, idempotent, with a lease
--   learning_input_rejections   sanitized isolation of a malformed/lineage-less input — source
--                               identity + reason ONLY, never the forbidden raw value
--   learning_object_evaluations append-only: every actual per-run decision (new or held object),
--                               so reproducibility never requires mutating a proposal
--
-- All statements idempotent; org cascades per 0033/0043/0045.

-- ---------------------------------------------------------------------------------------
-- Trusted structured inbox. (tenant, actor, source_ref) is idempotent so a retry keeps the same
-- learning identity; observation time is the stored inbox time, not a retry wall clock.
create table if not exists learning_event_inbox (
    org_id           text not null,
    event_id         text not null,
    actor            text,
    source_ref       text not null,
    trace_id         text,
    independence_key text,
    visibility_scope text not null default 'private',
    visibility       jsonb,
    lease_until      timestamptz,
    payload          jsonb not null,
    observed_at      timestamptz not null,
    created_at       timestamptz not null default now(),
    primary key (org_id, event_id)
);
create unique index if not exists learning_event_inbox_idem
    on learning_event_inbox (org_id, actor, source_ref);
comment on table learning_event_inbox is
  'L6 trusted structured events/memory. (org,actor,source_ref) idempotent; observed_at is the stored inbox time so retries keep one learning identity.';

-- ---------------------------------------------------------------------------------------
-- Sanitized rejections. One malformed optional input cannot poison the rest of a run, and the
-- forbidden raw value is never retained — only its source identity/hash and a reason code.
create table if not exists learning_input_rejections (
    id           text primary key,
    org_id       text not null,
    seam         text not null,               -- outcomes | delivery | enterprise | feedback | inbox
    source_ref   text,
    source_hash  text,
    reason_code  text not null,
    created_at   timestamptz not null default now()
);
create index if not exists learning_input_rejections_by_org
    on learning_input_rejections (org_id, created_at);

-- ---------------------------------------------------------------------------------------
-- Append-only evaluation ledger: the final transition/publisher outcome of each actual decision,
-- pinned to the exact run + policy revision + evaluation time. Publish success, no-material-change
-- and metric-identity conflicts stay distinguishable, and object replay never mutates the proposal.
create table if not exists learning_object_evaluations (
    id               text primary key,
    org_id           text not null,
    run_id           text not null,
    learning_id      text not null,
    policy_revision  int  not null,
    evaluated_at     timestamptz not null,
    prior_state      text,
    result_state     text not null,
    object_inserted  boolean not null default false,
    sink_reason      text not null,           -- published_to_dynamic_target | no_material_change | metric_identity_conflict | ...
    created_at       timestamptz not null default now()
);
create index if not exists learning_object_evaluations_replay
    on learning_object_evaluations (org_id, learning_id, evaluated_at);
create index if not exists learning_object_evaluations_by_run
    on learning_object_evaluations (org_id, run_id);

-- ---------------------------------------------------------------------------------------
alter table learning_event_inbox        add constraint learning_event_inbox_org_cascade_fk        foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_input_rejections   add constraint learning_input_rejections_org_cascade_fk   foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_object_evaluations add constraint learning_object_evaluations_org_cascade_fk foreign key (org_id) references orgs (id) on delete cascade not valid;

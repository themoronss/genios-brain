-- GeniOS Engine · Atlas Layer 6 — governed Learning & Evolution.
--
-- The immutable proposal (`learning_objects.payload`) is separated from mutable lifecycle state.
-- Publication is an append-only, versioned write into one of three dynamic brains, runtime memory
-- or metrics.  There is deliberately no Expert Brain table or publisher: knowledge drift lands in
-- `knowledge_suggestions` and can only leave human review through an explicit decision.

create table if not exists learning_policies (
    org_id                  text not null,
    policy_key              text not null default 'default',
    learning_enabled        boolean not null default true,
    min_observations        int not null default 3,
    min_distinct_days       int not null default 2,
    min_confidence_bp       int not null default 6500,
    max_noise_bp            int not null default 2500,
    max_conflict_bp         int not null default 2500,
    min_business_value_bp   int not null default 1000,
    temporary_ttl_hours     int not null default 168,
    max_temporary_ttl_hours int not null default 720,
    require_human_targets   text[] not null default array['knowledge_suggestion','organization'],
    blocked_subject_prefixes text[] not null default array[]::text[],
    updated_by              text not null default 'system',
    updated_at              timestamptz not null default now(),
    primary key (org_id, policy_key),
    constraint learning_policy_counts_positive check
        (min_observations > 0 and min_distinct_days > 0),
    constraint learning_policy_bp_ranges check
        (min_confidence_bp between 0 and 10000 and max_noise_bp between 0 and 10000
         and max_conflict_bp between 0 and 10000 and min_business_value_bp between 0 and 10000),
    constraint learning_policy_ttl_range check
        (temporary_ttl_hours > 0 and max_temporary_ttl_hours >= temporary_ttl_hours)
);

create table if not exists learning_runs (
    run_id             text primary key,
    org_id             text not null,
    period_start       timestamptz not null,
    evaluation_time    timestamptz not null,
    source_window_days int not null default 28,
    status             text not null default 'started',
    units_planned      text[] not null default array[]::text[],
    objects_observed   int not null default 0,
    objects_published  int not null default 0,
    objects_held       int not null default 0,
    objects_rejected   int not null default 0,
    result             jsonb not null default '{}',
    completed_at       timestamptz,
    created_at         timestamptz not null default now(),
    constraint learning_runs_status check (status in ('started','completed','failed')),
    constraint learning_run_counts_nonnegative check
        (objects_observed >= 0 and objects_published >= 0 and objects_held >= 0
         and objects_rejected >= 0),
    unique (org_id, period_start)
);

create table if not exists learning_objects (
    org_id             text not null,
    learning_id        text not null,
    semantic_hash      text not null,
    schema_version     text not null default 'learning.v1',
    unit_name          text not null,
    target_brain       text not null,
    subject_key        text not null,
    current_state      text not null default 'observed',
    confidence_bp      int not null,
    observations       int not null,
    distinct_days      int not null,
    positive_evidence  int not null default 0,
    negative_evidence  int not null default 0,
    noise_bp           int not null default 0,
    conflict_bp        int not null default 0,
    business_value_bp  int not null default 5000,
    requires_review    boolean not null default false,
    policy_key         text not null default 'default',
    source_run_id      text,
    payload             jsonb not null,
    observed_at        timestamptz not null,
    expires_at         timestamptz,
    published_at       timestamptz,
    updated_at         timestamptz not null default now(),
    primary key (org_id, learning_id),
    constraint learning_object_target check
        (target_brain in ('organization','behavior','adaptive','runtime','metrics',
                          'knowledge_suggestion')),
    constraint learning_object_state check
        (current_state in ('observed','candidate','validated','governed','temporary',
                           'human_review','promoted','published','rejected','expired',
                           'superseded','rolled_back')),
    constraint learning_object_evidence check
        (confidence_bp between 0 and 10000 and noise_bp between 0 and 10000
         and conflict_bp between 0 and 10000 and business_value_bp between 0 and 10000
         and observations >= 0 and distinct_days >= 0 and positive_evidence >= 0
         and negative_evidence >= 0 and positive_evidence + negative_evidence <= observations),
    constraint learning_runtime_has_ttl check
        ((target_brain = 'runtime' and expires_at is not null)
         or (target_brain <> 'runtime' and expires_at is null)),
    constraint learning_knowledge_review_only check
        (unit_name <> 'knowledge_evolution' or target_brain = 'knowledge_suggestion'),
    unique (org_id, semantic_hash)
);

create index if not exists learning_objects_queue
    on learning_objects (org_id, current_state, observed_at);
create index if not exists learning_objects_subject
    on learning_objects (org_id, target_brain, subject_key, observed_at desc);

create table if not exists learning_transitions (
    transition_id  text primary key,
    org_id         text not null,
    learning_id    text not null,
    from_state     text,
    to_state       text not null,
    reason_code    text not null,
    actor           text not null default 'system',
    detail          jsonb not null default '{}',
    occurred_at    timestamptz not null default now()
);

create index if not exists learning_transitions_object
    on learning_transitions (org_id, learning_id, occurred_at);

create table if not exists learned_brain_entries (
    org_id         text not null,
    entry_id       text not null,
    brain          text not null,
    subject_key    text not null,
    version        int not null,
    value           jsonb not null,
    confidence_bp  int not null,
    learning_id    text not null,
    active          boolean not null default true,
    effective_at   timestamptz not null,
    ended_at       timestamptz,
    ended_reason   text,
    created_at     timestamptz not null default now(),
    primary key (org_id, entry_id),
    constraint learned_brain_target check (brain in ('organization','behavior','adaptive')),
    constraint learned_brain_confidence check (confidence_bp between 0 and 10000),
    unique (org_id, brain, subject_key, version)
);

create unique index if not exists learned_brain_one_active
    on learned_brain_entries (org_id, brain, subject_key) where active;

create table if not exists temporary_memories (
    org_id       text not null,
    memory_id    text not null,
    subject_key  text not null,
    value         jsonb not null,
    learning_id  text not null,
    confidence_bp int not null,
    observed_at  timestamptz not null,
    expires_at   timestamptz not null,
    expired_at   timestamptz,
    created_at   timestamptz not null default now(),
    primary key (org_id, memory_id),
    constraint temporary_memory_lease check (expires_at > observed_at),
    constraint temporary_memory_confidence check (confidence_bp between 0 and 10000),
    unique (org_id, learning_id)
);

create index if not exists temporary_memories_active
    on temporary_memories (org_id, expires_at) where expired_at is null;

create table if not exists knowledge_suggestions (
    org_id       text not null,
    suggestion_id text not null,
    learning_id  text not null,
    subject_key  text not null,
    suggestion    jsonb not null,
    evidence      jsonb not null,
    status        text not null default 'pending',
    decided_by   text,
    decided_at   timestamptz,
    decision_note text,
    created_at   timestamptz not null default now(),
    primary key (org_id, suggestion_id),
    constraint knowledge_suggestion_status check
        (status in ('pending','approved','rejected','withdrawn')),
    unique (org_id, learning_id)
);

create table if not exists learning_metrics (
    org_id       text not null,
    metric_id    text not null,
    metric_key   text not null,
    period_start timestamptz not null,
    period_end   timestamptz not null,
    value         jsonb not null,
    learning_id  text not null,
    created_at   timestamptz not null default now(),
    primary key (org_id, metric_id),
    constraint learning_metric_window check (period_end > period_start),
    unique (org_id, metric_key, period_start, period_end)
);

-- Direct org ownership is deliberate even where another org-owned row is also referenced. It
-- keeps account erasure schema-enforced and independently auditable for every learned artifact.
alter table learning_policies add constraint learning_policies_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_runs add constraint learning_runs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_objects add constraint learning_objects_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_transitions add constraint learning_transitions_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learned_brain_entries add constraint learned_brain_entries_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table temporary_memories add constraint temporary_memories_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table knowledge_suggestions add constraint knowledge_suggestions_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_metrics add constraint learning_metrics_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table learned_brain_entries is
  'Versioned Organization, Behavior and Adaptive brain state published by governed learning.';
comment on table knowledge_suggestions is
  'Human-review-only Expert Brain change suggestions. Approval records intent; it never edits Git.';

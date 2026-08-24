-- GeniOS Engine · Layer 6 — Learning & Evolution baseline ledgers (= the spec's 0045).
--
-- Layer 6 learns from OUTCOMES, not clicks. It records a proposal (an immutable LearningObject)
-- before it changes any state, lets governance override confidence, expires temporary memory, and
-- can never edit the Expert Brain. These eight ledgers are the durable spine:
--
--   learning_policies      versioned governance authority (one active revision per tenant)
--   learning_runs          the weekly per-tenant claim + its counts
--   learning_objects       immutable content-addressed proposals; lifecycle lives in a column set
--   learning_transitions   append-only state history (never rewrites the object)
--   learned_brain_entries  published org/behavior/adaptive brain values, versioned
--   temporary_memories     Runtime leases with a mandatory expiry
--   knowledge_suggestions  human-review queue; NEVER an Expert-Brain write
--   learning_metrics       measurement artifacts (not a brain)
--
-- Lifecycle columns are SEPARATE from the object's evidence/identity so a transition never
-- rewrites what the object was hashed on. All statements idempotent; org cascades per 0033/0043.

-- ---------------------------------------------------------------------------------------
create table if not exists learning_policies (
    org_id                        text not null,
    revision                      int  not null,
    snapshot                      jsonb not null,           -- immutable full policy snapshot
    min_observations              int  not null default 3,
    min_distinct_days             int  not null default 2,
    min_confidence_bp             int  not null default 6000,
    max_noise_bp                  int  not null default 4000,
    max_conflict_bp               int  not null default 3000,
    max_runtime_ttl_seconds       int  not null default 604800,
    organization_requires_review  boolean not null default true,
    knowledge_requires_review     boolean not null default true,
    learning_enabled              boolean not null default true,
    blocked_targets               jsonb,
    blocked_subject_prefixes      jsonb,
    created_at                    timestamptz not null default now(),
    primary key (org_id, revision),
    constraint learning_policies_knowledge_review_locked check (knowledge_requires_review)
);
comment on table learning_policies is
  'Versioned Layer 6 governance. Each revision is an immutable snapshot; runs/objects pin an exact revision. knowledge_requires_review is CHECK-locked true — it can never be disabled.';

-- ---------------------------------------------------------------------------------------
create table if not exists learning_runs (
    org_id           text not null,
    run_id           text not null,
    week_key         text not null,               -- tenant/week claim identity
    policy_revision  int  not null,
    evaluated_at     timestamptz not null,
    status           text not null default 'claimed',  -- claimed | completed | failed
    attempt          int  not null default 1,
    error_class      text,                        -- sanitized; never a raw payload
    objects_inserted int  not null default 0,
    objects_unchanged int not null default 0,
    counts           jsonb,
    created_at       timestamptz not null default now(),
    completed_at     timestamptz,
    primary key (org_id, run_id)
);
create unique index if not exists learning_runs_week
    on learning_runs (org_id, week_key);

-- ---------------------------------------------------------------------------------------
create table if not exists learning_objects (
    org_id            text not null,
    learning_id       text not null,              -- content-addressed stable id
    schema_version    text not null default 'learning.v2',
    unit              text not null,
    target            text not null,              -- organization|behavior|adaptive|runtime|metrics|knowledge_suggestion
    subject           text not null,
    semantic_hash     text not null,
    proposed_value    jsonb not null,
    evidence          jsonb not null,
    visibility_scope  text not null,              -- private|participants|organization|public
    visibility        jsonb not null,
    lineage_complete  boolean not null default true,
    subject_principal text,
    policy_key        text not null,
    policy_revision   int,
    first_seen_at     timestamptz not null,
    last_seen_at      timestamptz not null,
    expires_at        timestamptz,                -- Runtime target only
    state             text not null default 'observed',
    created_at        timestamptz not null default now(),
    closed_at         timestamptz,
    primary key (org_id, learning_id),
    constraint learning_objects_no_expert check (target <> 'expert'),
    constraint learning_objects_runtime_expiry
        check (expires_at is null or target = 'runtime')
);
create index if not exists learning_objects_open
    on learning_objects (org_id, target, state) where closed_at is null;
create index if not exists learning_objects_cohort
    on learning_objects (org_id, unit, subject);

-- ---------------------------------------------------------------------------------------
create table if not exists learning_transitions (
    id            text primary key,
    org_id        text not null,
    learning_id   text not null,
    from_state    text,
    to_state      text not null,
    reason_code   text not null,
    actor         text,
    detail        jsonb,
    occurred_at   timestamptz not null default now()
);
create index if not exists learning_transitions_by_object
    on learning_transitions (org_id, learning_id, occurred_at);

-- ---------------------------------------------------------------------------------------
-- Published brain values. One active version per (tenant, brain, subject); supersession bumps
-- max(version)+1, restoration links to the exact predecessor. ACL preserved exactly.
create table if not exists learned_brain_entries (
    org_id          text not null,
    brain           text not null,               -- organization|behavior|adaptive
    subject         text not null,
    version         int  not null,
    learning_id     text not null,
    value           jsonb not null,
    visibility_scope text not null,
    visibility      jsonb not null,
    active          boolean not null default true,
    supersedes      int,
    created_at      timestamptz not null default now(),
    deactivated_at  timestamptz,
    primary key (org_id, brain, subject, version),
    constraint learned_brain_no_expert check (brain in ('organization','behavior','adaptive'))
);
create unique index if not exists learned_brain_one_active
    on learned_brain_entries (org_id, brain, subject) where active;

-- ---------------------------------------------------------------------------------------
create table if not exists temporary_memories (
    org_id       text not null,
    memory_id    text not null,
    learning_id  text,
    subject      text not null,
    value        jsonb not null,
    visibility_scope text not null,
    visibility   jsonb not null,
    expires_at   timestamptz not null,           -- mandatory; a Runtime lease always has a clock
    active       boolean not null default true,
    created_at   timestamptz not null default now(),
    primary key (org_id, memory_id)
);
create index if not exists temporary_memories_active
    on temporary_memories (org_id, expires_at) where active;

-- ---------------------------------------------------------------------------------------
create table if not exists knowledge_suggestions (
    org_id       text not null,
    suggestion_id text not null,
    learning_id  text,
    subject      text not null,
    body         jsonb not null,
    state        text not null default 'human_review',  -- never auto-applies; expert_brain_changed stays false
    reviewed_by  text,
    reviewed_at  timestamptz,
    created_at   timestamptz not null default now(),
    primary key (org_id, suggestion_id)
);

-- ---------------------------------------------------------------------------------------
create table if not exists learning_metrics (
    org_id       text not null,
    metric_id    text not null,
    learning_id  text,
    unit         text not null,
    subject      text not null,
    value        jsonb not null,
    observed_at  timestamptz not null,
    created_at   timestamptz not null default now(),
    primary key (org_id, metric_id)
);
create index if not exists learning_metrics_cohort
    on learning_metrics (org_id, unit, subject, observed_at);

-- ---------------------------------------------------------------------------------------
-- Account erasure paths (NOT VALID, per 0033/0043).
alter table learning_policies      add constraint learning_policies_org_cascade_fk       foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_runs          add constraint learning_runs_org_cascade_fk           foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_objects       add constraint learning_objects_org_cascade_fk        foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_transitions   add constraint learning_transitions_org_cascade_fk    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learned_brain_entries  add constraint learned_brain_entries_org_cascade_fk   foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table temporary_memories     add constraint temporary_memories_org_cascade_fk      foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table knowledge_suggestions  add constraint knowledge_suggestions_org_cascade_fk   foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table learning_metrics       add constraint learning_metrics_org_cascade_fk        foreign key (org_id) references orgs (id) on delete cascade not valid;

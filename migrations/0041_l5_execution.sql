-- GeniOS Engine · L5 Executive Engine — the commitment, and everything that happens to it.
--
-- Until now Layer 5 produced a card and stopped. A card is a *statement*: it says what should
-- happen, it waits to be looked at, and if nobody looks at it, nothing anywhere records that
-- fact. The layer had no answer to "did it get done?", so it had nothing to remind about,
-- nothing to escalate, and nothing to learn from beyond which buttons got clicked.
--
-- These tables give a recommendation a life. `executions` is the commitment: one live row per
-- Layer 4 decision, carrying the frozen plan, its owner, its channel, its deadline and its
-- state. Everything else hangs off it — the steps, the escalation ladder, the audit trail, and
-- the outcome record Layer 6 Learning will learn from.
--
-- Three design points are worth reading before changing anything here.
--
-- 1. IDENTITY IS THE DECISION, NOT THE ROUTING. `executions_one_per_decision` is unique on
--    (org_id, decision_hash) among OPEN rows. Re-running the sweep over the same decision must
--    not mint a second commitment; reassigning one to a different person must not either.
--    Closing a row frees the key, which is how a superseding re-plan lands cleanly.
--
-- 2. THE PLAN IS IMMUTABLE, THE ROW IS NOT. `payload` holds the content-addressed
--    ExecutionObject exactly as it was built. State, owner, counters and timestamps move; the
--    plan and the ladder never do. That is what makes "why did this escalate on day 7?"
--    answerable after the pack has been retuned twice.
--
-- 3. NOTHING FIRES WITHOUT RE-VALIDATION. `next_check_at` drives the sweep, but a due row is
--    only a candidate — executive/execution_guard.py re-checks live state before every
--    delivery, reminder and escalation. The scheduler decides *when to look*, never *whether to
--    send*. A reminder about something that already happened costs more trust than ten missed
--    ones.
--
-- Table and index statements are idempotent. The cascade constraints at the bottom are plain
-- ALTERs, matching 0033's convention — the schema_migrations ledger runs each file once.

-- ---------------------------------------------------------------------------------------
-- The reporting line. org_seats has always had role (admin|member) and no hierarchy, which
-- meant an escalation to "the manager" had nowhere to go and fell back to the admin list.
-- Nullable: orgs that publish no hierarchy keep exactly today's behaviour.
alter table org_seats add column if not exists manager_seat_id text;

create index if not exists org_seats_by_manager on org_seats (org_id, manager_seat_id)
    where manager_seat_id is not null;

comment on column org_seats.manager_seat_id is
  'Optional reporting line. executive/assignment.py resolve_escalation_target() uses it; falls back to active admins when null.';


-- ---------------------------------------------------------------------------------------
-- The commitment.
create table if not exists executions (
    org_id              text not null,
    execution_id        text not null,                  -- content address of (org, decision, plan)
    decision_hash       text not null,                  -- the L4 decision this commits to
    reasoning_run_id    text not null,
    candidate_id        text not null,
    context_snapshot_id text not null,
    config_snapshot_id  text not null,
    capability_id       text not null,
    capability_version  text not null,
    play_id             text,
    plan_hash           text not null,
    plan_revision       int  not null default 1,

    state               text not null default 'created',
        -- created | pending | running | waiting | blocked | completed | cancelled | expired | archived
    goal                text not null,
    subject_ref         text,
    subject_type        text,

    -- Communication plan. Layer 5 owns who and where (see docs/LAYER_MAP.md); Layer 5.2 executes it.
    assignee            text,
    audience            text not null default 'owner',
    channel_id          text not null default 'in_app',
    channel_class       text not null default 'in_app',
    interrupt           boolean not null default false,
    routing_rule        text not null default 'rule3_unrouted',

    priority_bp         int  not null,
    confidence_bp       int  not null,
    band                text not null default 'standard',

    created_at          timestamptz not null default now(),
    deadline_at         timestamptz not null,
    expires_at          timestamptz not null,
    next_check_at       timestamptz,                    -- when the sweep should look again
    delivered_at        timestamptz,
    first_touch_at      timestamptz,                    -- when a human first engaged
    closed_at           timestamptz,
    close_reason        text,
    superseded_by       text,

    reminder_count      int  not null default 0,
    last_reminded_at    timestamptz,
    escalation_count    int  not null default 0,

    card_id             text,                           -- the L6 surface, once one exists
    signal_id           text,
    payload             jsonb not null,                 -- the frozen ExecutionObject
    updated_at          timestamptz not null default now(),

    primary key (org_id, execution_id)
);

-- One live commitment per decision. Partial on closed_at so a superseded re-plan can land while
-- the history it replaces stays on the table.
create unique index if not exists executions_one_per_decision
    on executions (org_id, decision_hash) where closed_at is null;

comment on index executions_one_per_decision is
  'Idempotence key for the L5 sweep: re-planning the same L4 decision updates rather than duplicating. Partial so closed commitments do not block a superseding re-plan.';

-- The sweep's only scan. Every open commitment carries its own next meaningful moment, so the
-- reminder pass is a due-time query rather than a full walk of every open row on every run.
create index if not exists executions_due
    on executions (next_check_at) where closed_at is null;

comment on index executions_due is
  'Drives executive/execution_store.py due_executions(). A due row is a candidate only — execution_guard re-validates before anything fires.';

create index if not exists executions_by_assignee
    on executions (org_id, assignee, state) where closed_at is null;

create index if not exists executions_by_subject
    on executions (org_id, subject_ref) where closed_at is null;

-- Outcome reporting and the Layer 6 Learning feed both read closed rows by pack cohort and time.
create index if not exists executions_closed_at
    on executions (org_id, closed_at) where closed_at is not null;


-- ---------------------------------------------------------------------------------------
-- The steps. Denormalised out of the payload because "what is this person actually blocked on"
-- is a per-action question the UI asks constantly, and digging it out of jsonb on every render
-- would make the commitment list quadratic in plan length.
create table if not exists execution_actions (
    org_id            text not null,
    execution_id      text not null,
    action_id         text not null,
    ordinal           int  not null,
    stage             int  not null,
    kind              text not null,
    label             text not null,
    requires_approval boolean not null default false,
    read_only         boolean not null default true,
    deadline_at       timestamptz,
    completed_at      timestamptz,
    completed_by      text,
    primary key (org_id, execution_id, action_id)
);

create index if not exists execution_actions_open
    on execution_actions (org_id, execution_id, ordinal) where completed_at is null;


-- ---------------------------------------------------------------------------------------
-- The ladder, one row per rung. Rows are written at build time with fired_at null: the plan
-- commits to the schedule up front, and firing is a fact recorded against it. Driving
-- escalation off "which rungs have not fired" rather than off a cursor means a sweep that
-- missed a day (deploy, outage, paused org) catches up instead of silently skipping.
create table if not exists execution_escalations (
    org_id       text not null,
    execution_id text not null,
    day_offset   int  not null,
    action       text not null,                        -- notify | remind | escalate | critical
    audience     text not null,
    interrupt    boolean not null default false,
    fires_at     timestamptz not null,
    fired_at     timestamptz,
    target_seat  text,                                 -- resolved at fire time, not plan time
    reason_code  text not null,
    primary key (org_id, execution_id, day_offset)
);

create index if not exists execution_escalations_due
    on execution_escalations (fires_at) where fired_at is null;

comment on index execution_escalations_due is
  'Catch-up index: unfired rungs whose time has come. Deliberately not a cursor — a missed sweep must not silently skip a rung.';


-- ---------------------------------------------------------------------------------------
-- The audit trail. Every state move, reminder, escalation and suppression, with its cause.
-- A state column alone answers "what"; support incidents need "why", and they need it after
-- the fact, which means it has to be written at the time.
create table if not exists execution_events (
    event_id     text primary key,
    org_id       text not null,
    execution_id text not null,
    kind         text not null,                        -- execution.* (executive/lifecycle.py)
    reason_code  text not null,
    actor        text not null default 'system',
    from_state   text,
    to_state     text,
    detail       jsonb not null default '{}',
    occurred_at  timestamptz not null default now()
);

create index if not exists execution_events_by_execution
    on execution_events (org_id, execution_id, occurred_at);

create index if not exists execution_events_by_kind
    on execution_events (org_id, kind, occurred_at);


-- ---------------------------------------------------------------------------------------
-- The outcome record — the Layer 5→Layer 6 Learning seam.
--
-- Layer 6 Learning learns today from card judgments: what a human clicked when a recommendation arrived.
-- That measures whether it LOOKED right, not whether acting on it WORKED. These rows measure the
-- second thing, including the attention it cost to get there (reminders_sent, escalations_fired)
-- — a play that succeeds once per four reminders is not obviously better than one that fails
-- quietly, and no click metric can tell them apart.
create table if not exists execution_outcomes (
    outcome_id          text primary key,
    org_id              text not null,
    execution_id        text not null,
    decision_hash       text not null,
    capability_id       text not null,
    capability_version  text not null,
    play_id             text not null,
    play_version        text not null,
    terminal_state      text not null,
    reason_code         text not null,
    label               text not null,
        -- succeeded | completed_unproven | expired_untouched | expired_in_progress
        -- | cancelled_by_human | cancelled_by_world | cancelled_by_system
    created_at          timestamptz not null,
    closed_at           timestamptz not null,
    seconds_to_close    bigint not null,
    actions_total       int not null,
    actions_completed   int not null,
    progress_bp         int not null,
    reminders_sent      int not null default 0,
    escalations_fired   int not null default 0,
    priority_bp         int not null,
    confidence_bp       int not null,
    band                text not null,
    routing_rule        text not null,
    outcome_kind        text,
    outcome_observed_at timestamptz,
    assignee            text,
    subject_ref         text,
    payload             jsonb not null default '{}',
    recorded_at         timestamptz not null default now()
);

-- One outcome per commitment. A commitment ends once; a second row would double-count it in
-- every precision calculation Layer 6 Learning runs.
create unique index if not exists execution_outcomes_once
    on execution_outcomes (org_id, execution_id);

create index if not exists execution_outcomes_cohort
    on execution_outcomes (org_id, capability_id, play_id, closed_at);

comment on index execution_outcomes_cohort is
  'The Layer 6 learning read: outcomes per play per window. Ordered by closed_at so calibration windows are a range scan.';


-- ---------------------------------------------------------------------------------------
-- Account erasure. Every org-scoped table needs a schema-enforced delete path to orgs, and
-- tests/test_account_erasure.py proves it for the whole schema rather than trusting a checklist
-- — a commitment that outlived its tenant's deletion request is a compliance incident, not a
-- stale row. Same `not valid` convention as 0033: the constraint binds all future writes without
-- taking a full-table lock to re-check history on deploy.
alter table executions add constraint executions_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table execution_actions add constraint execution_actions_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table execution_escalations add constraint execution_escalations_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table execution_events add constraint execution_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table execution_outcomes add constraint execution_outcomes_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

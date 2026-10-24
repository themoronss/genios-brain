-- 0254 · the goal object (GeniOS-012 S28.U1; `speedrun008/GeniOS-008/00-ARCHITECTURE.md` "Goals", amended 23 Oct).
--
-- A goal is an object L3 owns (`context/goals`). Every change is a NEW REVISION ROW, never an overwrite: the latest
-- revision of a goal is the goal. Born from the company brief (D11): an accepted `goals` line is an approved goal, a
-- pending one a proposed goal, and L3 syncs this table from the brief every sweep (`context/goals.sync_from_brief`).
--
-- A HUMAN MAKES A GOAL REAL: `approved` and `active` require who approved it and when — a check constraint, not a
-- convention. Nothing a model or code writes is ever approved.
--
-- `goal_situation_links`: what a move's `GoalImpact` links, written only when the situation is ADMITTED and the goal is
-- live (S30.U1). Idempotent: safe to run twice.

create table if not exists company_goals (
    org_id          text        not null,
    goal_id         text        not null,
    revision        integer     not null,
    statement       text        not null check (length(statement) between 1 and 200),
    status          text        not null check (status in ('proposed', 'approved', 'active', 'completed',
                                                            'superseded', 'cancelled')),
    source          text        not null check (source in ('founder', 'brief', 'inferred')),
    line_id         text,
    department      text,
    category        text,
    owner_seat      text,
    metric          text,
    target          text,
    deadline        text,
    parent_goal_id  text,
    subject_ref     text,
    evidence_refs   jsonb       not null default '[]'::jsonb,
    approved_by     text,
    approved_at     timestamptz,
    created_at      timestamptz not null default now(),
    primary key (org_id, goal_id, revision),
    constraint company_goals_live_has_an_approver
        check (status not in ('approved', 'active') or (approved_by is not null and approved_at is not null))
);

create index if not exists company_goals_by_line on company_goals (org_id, line_id);

create table if not exists goal_situation_links (
    org_id              text        not null,
    goal_id             text        not null,
    situation_id        text        not null,
    relation            text        not null check (relation in ('advances', 'threatens', 'depends_on', 'unclear')),
    why                 text        not null,
    evidence            jsonb       not null default '[]'::jsonb,
    result_fingerprint  text,
    linked_at           timestamptz not null default now(),
    primary key (org_id, goal_id, situation_id)
);

comment on table company_goals is
  'GeniOS-012 S28.U1 · the goal object, one row per revision (latest = the goal). Synced from company brief goals lines by L3 every sweep; approved/active require approved_by + approved_at.';
comment on table goal_situation_links is
  'GeniOS-012 S28.U1/S30.U1 · a move''s GoalImpact on an ADMITTED situation of a LIVE goal.';

-- 0151 · TEAM MILESTONES — what a readiness report (P-12) is measured against (SCREEN_INTEL_P4 §3.2).
--
-- A milestone is a dated goal with an owner seat ("ISO audit", 19 Sep, Emru). Readiness counts are
-- computed on read and in the team post-pass, never stored: done / pending from `task` nodes that
-- match `task_filter` (a connected tracker such as Linear), away = seats with an absence window
-- between now and the due date. `scope_kind` / `scope_key` narrow "the team" to the seats that
-- answer for that slice (`seat_responsibilities`); empty = the whole org.
create table if not exists team_milestones (
    milestone_id  text primary key,
    org_id        text not null references orgs (id) on delete cascade,
    title         text not null,
    due_at        timestamptz not null,
    owner_seat_id text not null,
    scope_kind    text,
    scope_key     text,
    task_filter   jsonb not null default '{}'::jsonb,
    created_by    text,
    created_at    timestamptz not null default now(),
    archived_at   timestamptz,
    constraint team_milestones_title check (length(btrim(title)) between 1 and 200)
);
create index if not exists team_milestones_by_org on team_milestones (org_id, due_at)
    where archived_at is null;

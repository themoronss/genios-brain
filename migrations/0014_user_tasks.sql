-- 0014 — user task ledger (the dashboard "Today" quick-add). Plain per-org CRUD, no intelligence:
-- the founder jots reminders ("msg Isha next week") and the manager-brief nags them when overdue.
create table if not exists user_tasks (
    id            text primary key,
    org_id        text not null,
    text          text not null,
    target_entity text,
    due_at        timestamptz,
    status        text not null default 'open',   -- open | done | snoozed | dropped
    source        text not null default 'manual',
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists ix_user_tasks_org on user_tasks (org_id, status);

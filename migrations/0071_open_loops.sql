-- L2-16: the open-loop ledger — the unit completion actually closes.
--
-- Completion authority was the person-wide thread.ball_in_court bit, so answering any of
-- somebody's three questions read as answering all of them, and a card expiring was
-- indistinguishable from the request resolving (11 subjects carried the same expired/reopened
-- signal pairing). This table gives each REQUEST its own row: opened by an ask-class
-- observation, bumped by a repeat, closed by OUR reply on its thread — and reopened if they
-- ask again after we answered.
create table if not exists open_loops (
    org_id           text not null references orgs(id) on delete cascade,
    loop_id          text not null,
    subject_node_id  text not null,
    kind             text not null,
    thread_id        text,
    status           text not null default 'open' check (status in ('open', 'closed')),
    opened_at        timestamptz not null,
    last_seen_at     timestamptz not null,
    ask_count        int not null default 1,
    opened_by_event  text not null,
    closed_at        timestamptz,
    closed_by_event  text,
    primary key (org_id, loop_id)
);
create index if not exists open_loops_subject on open_loops (org_id, subject_node_id)
    where status = 'open';
create index if not exists open_loops_thread on open_loops (org_id, thread_id)
    where status = 'open';

comment on table open_loops is
  'One row per unresolved request (loop_id = contracts/open_loop.open_loop_id). A match closes ONE request, never a person.';

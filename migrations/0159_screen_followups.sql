-- 0159 · SCREEN FOLLOW-UPS + THREAD VERDICTS (SCREEN_INTEL_MANAGER_VALUE_BUILD.md C4, C9).
--
-- A follow-up is what a screen insight leaves behind: an ask waiting on the seat, a promise the
-- seat made (my_promise) or was made (their_promise), a deadline, a risk, a next step. It feeds
-- the device's brief / wrap / nudges and the weekly report. `text` is the MODEL'S NOTE (≤ 140
-- chars) — never screen text. One row per topic (`topic_key` = seat | thread | kind | who | local
-- day): a repeat of the same topic updates the row instead of adding one.
--
-- Resolved rows stay (the weekly report counts them): answered (structural: a `You:` line after
-- the ask), done / dismissed (the person), expired (a promise 2 days past due).
create table if not exists screen_followups (
    id          text primary key,                   -- 'fu_…'
    org_id      text not null references orgs (id) on delete cascade,
    seat_id     text not null,
    thread_key  text,
    app         text,
    kind        text not null,
    text        text not null,
    who         text,
    due_at      timestamptz,
    nudge_at    timestamptz,
    topic_key   text not null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    resolved_at timestamptz,
    resolution  text,
    constraint screen_followups_kind check (kind in
        ('ask', 'my_promise', 'their_promise', 'deadline', 'risk', 'next_step')),
    constraint screen_followups_resolution check (resolution is null or resolution in
        ('answered', 'done', 'dismissed', 'expired')),
    constraint screen_followups_text check (char_length(text) <= 140),
    constraint screen_followups_topic unique (org_id, seat_id, topic_key)
);
-- The slice / list (open, newest first) and the ask-answered check (open asks of one thread).
create index if not exists screen_followups_open
    on screen_followups (org_id, seat_id, created_at desc) where resolved_at is null;
-- `removed_followups` (resolved since the device's slice version).
create index if not exists screen_followups_resolved
    on screen_followups (org_id, seat_id, resolved_at) where resolved_at is not null;

-- The model's latest "is this thread work?" judgement per (seat, thread). Read by the screen
-- relevance gate (C9): a verdict from the last 24 h routes the thread's memory (work → keep,
-- personal → park) with no AI gate call.
create table if not exists screen_thread_verdicts (
    org_id     text not null references orgs (id) on delete cascade,
    seat_id    text not null,
    thread_key text not null,
    work       boolean not null,
    judged_at  timestamptz not null default now(),
    primary key (org_id, seat_id, thread_key)
);

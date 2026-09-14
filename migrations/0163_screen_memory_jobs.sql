-- 0163 · SCREEN MEMORY BATCH (SCREEN_INTEL_SYSTEM_DESIGN.html, phase 1 step S4 — the hourly
-- short memory update via the Anthropic Message Batches API).
--
-- In "instant" screen-memory mode the only memory is the instant judge's items. A promoted thread
-- the judge never saw (daily cap, timeout, messages scrolled past) would never reach memory, so
-- the promoter enqueues ONE job per promoted, not-personal thread here; the promoter's daemon
-- thread (reason/moments/screen_memory_batch.py `tick`) submits queued jobs as one batch and
-- later reads the results into follow-ups, graph observations and a short thread summary.
--
-- screen_memory_jobs
--   text_enc     the promoted thread's rendered text (last 6000 chars), Fernet-encrypted; set to
--                NULL once the job's result is processed (done / skipped / failed) — screen text
--                is never kept longer than it is needed.
--   status       queued → submitted (batch_id set) → done | skipped (judged personal) | failed
--                (3 errored / expired results); an errored result goes back to queued.
-- screen_thread_summaries
--   summary      ≤ 3 short lines the model wrote about the thread, for later context (the
--                model's words, never screen text); one row per (org, seat, thread).
create table if not exists screen_memory_jobs (
    id           text primary key,                  -- 'smj_…'
    org_id       text not null references orgs (id) on delete cascade,
    seat_id      text not null,
    thread_key   text not null,
    app          text,
    event_id     text not null,
    text_enc     bytea,
    status       text not null default 'queued',
    batch_id     text,
    attempts     int not null default 0,
    error        text,
    created_at   timestamptz not null default now(),
    submitted_at timestamptz,
    finished_at  timestamptz,
    result       jsonb,
    constraint screen_memory_jobs_status check (status in
        ('queued', 'submitted', 'done', 'failed', 'skipped'))
);
-- the tick's two reads: the oldest queued jobs, and the submitted ones per batch
create index if not exists screen_memory_jobs_status_created
    on screen_memory_jobs (status, created_at);

create table if not exists screen_thread_summaries (
    org_id     text not null references orgs (id) on delete cascade,
    seat_id    text not null,
    thread_key text not null,
    summary    text not null,
    updated_at timestamptz not null default now(),
    primary key (org_id, seat_id, thread_key)
);

-- Durable sync jobs — the production-grade replacement for fire-and-forget BackgroundTasks.
-- A Sync click ENQUEUES a row here; an in-process worker claims and runs it, heart-beating +
-- checkpointing as it goes. If the process dies mid-run (deploy / OOM / worker recycle), the job
-- stays 'running' with a stale heartbeat and the next worker RE-CLAIMS and resumes it from the
-- checkpoint — so the sync completes regardless of restarts, and the user can close the tab.
--
-- The client never drives the work; it only reads onboarding_progress for display.

create table if not exists sync_jobs (
    id           text primary key,
    org_id       text not null,
    sources      jsonb not null default '[]'::jsonb,
    status       text  not null default 'queued',      -- queued | running | done | failed
    claimed_by   text,                                 -- worker instance id (for observability)
    heartbeat_at timestamptz,                          -- last liveness beat; stale => reclaimable
    attempts     int   not null default 0,
    checkpoint   jsonb not null default '{}'::jsonb,    -- {cursors:{gmail:..}, sources_done:[..]}
    error        text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create index if not exists sync_jobs_claim_idx on sync_jobs (status, heartbeat_at);

-- At most ONE active (queued or running) job per org — the durable overlap guard: a duplicate
-- Sync click can't spawn a competing job.
create unique index if not exists sync_jobs_active_org
    on sync_jobs (org_id) where status in ('queued', 'running');

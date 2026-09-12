-- WARM LANE · a new email / upload reaches graph + reasoning + cards in ~2 minutes, not 6 hours.
--
-- Three tables, one purpose: run the ingest -> L2 -> L4 -> cards chain for an org SOON after its
-- events land, ONCE per burst, and never twice at the same time.
--
-- `l2_work_queue` is a TRIGGER queue, not a data queue. The chain still pulls what it pulls
-- (`context/runner._pull`, off `qualified_signals`); a row here only says "this org has events that
-- arrived after the last run started". That is why coalescing is free — one run drains every
-- queued event of the org — and why a row is DONE exactly when a chain run that STARTED after the
-- row was enqueued completes, whoever ran it (warm worker, scheduler tick, a user's Sync job).
--
-- One pending row per (org_id, event_id): the partial unique index. An org-level trigger — a
-- chain caller that found the org busy and deferred — uses the event_id '*'.
create table if not exists l2_work_queue (
    id          bigserial primary key,
    org_id      text not null references orgs (id) on delete cascade,
    event_id    text not null,
    source      text not null,
    enqueued_at timestamptz not null default now(),
    -- claim lease: set by a worker when it claims the row, and reused as the retry "not before"
    -- after a failed run. A row whose lease has run out is claimable again (crash recovery).
    claimed_by  text,
    lease_until timestamptz,
    done_at     timestamptz,
    -- attempts ran out: parked for a human, never retried, never blocking a re-enqueue
    parked_at   timestamptz,
    attempts    integer not null default 0,
    last_error  text
);
create unique index if not exists l2_work_queue_one_pending
    on l2_work_queue (org_id, event_id) where done_at is null and parked_at is null;
-- The claim scan: open rows only, so the index holds the backlog and nothing else.
create index if not exists l2_work_queue_open
    on l2_work_queue (org_id, enqueued_at) where done_at is null and parked_at is null;
-- Retention prune of finished rows.
create index if not exists l2_work_queue_done
    on l2_work_queue (org_id, done_at) where done_at is not null;

-- SINGLE-FLIGHT per org, across every chain caller and every instance. A lease row, not an
-- advisory lock: the prod DB is a pooler, where a session lock outlives or escapes the caller.
-- Taken with one upsert that succeeds only if the row is absent, expired, or already ours;
-- heart-beaten while the chain runs; deleted on release. A crashed holder's lease simply expires.
create table if not exists org_run_leases (
    org_id       text primary key references orgs (id) on delete cascade,
    holder       text not null,
    lease_until  timestamptz not null,
    heartbeat_at timestamptz not null default now(),
    acquired_at  timestamptz not null default now()
);

-- GLOBAL warm-lane concurrency. `warm_lane_workers` slots in total, whatever the instance count:
-- a worker thread runs a chain only while it holds one. Same lease discipline as above. Kept
-- out of `org_run_leases` because a slot is not an org, and every org_id table cascades from orgs.
create table if not exists warm_lane_slots (
    slot         integer primary key,
    holder       text not null,
    lease_until  timestamptz not null,
    heartbeat_at timestamptz not null default now()
);

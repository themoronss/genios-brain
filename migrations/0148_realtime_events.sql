-- 0148 · REALTIME EVENTS — the transactional outbox behind `GET /v1/stream` (P3 §2.5, plan §9.6).
--
-- A writer inserts its event IN THE SAME TRANSACTION as the thing it announces (a moment, a slice
-- version bump, a policy change, a device revocation), so an event exists iff its cause committed.
-- One poller thread per process reads `seq > :last` once a second and fans out to the in-memory
-- subscribers of that process — no database connection is held per SSE client. `seq` is the SSE
-- `id:`, and `Last-Event-ID` replays from here.
--
-- `seat_id` NULL = every seat of the org (e.g. `policy.updated` for an org-wide policy change).
-- Kept 7 days (the in-process maintenance sweep deletes older rows); a client that was away longer
-- re-pulls its slice in full, which it does on every app start anyway.
create table if not exists realtime_events (
    seq        bigserial primary key,
    org_id     text not null references orgs (id) on delete cascade,
    seat_id    text,
    kind       text not null,
    payload    jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists realtime_events_by_seat on realtime_events (seat_id, seq);
-- Replay for one seat must also see the org-wide rows (seat_id NULL).
create index if not exists realtime_events_by_org on realtime_events (org_id, seq);
create index if not exists realtime_events_by_age on realtime_events (created_at);

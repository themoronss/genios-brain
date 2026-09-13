-- 0143 · SCREEN PROMOTION — held screen deltas become `screen_session` source events (P2).
--
-- The promoter (`platform/screen_promoter.py`) claims deltas per (org, seat) with
-- FOR UPDATE SKIP LOCKED plus a lease, exactly like the warm lane: a crashed worker's rows come
-- back when `lease_until` runs out, and `attempts` is counted at claim so a run that kills its
-- process still counts towards the park. `not_before` holds a retry back-off and the per-seat
-- generic cap's "next org-local midnight" — a deferred delta is never dropped.
--
-- status: held (waiting) · promoted (events landed, `event_ids`) · deferred (over the daily cap
-- or backing off) · parked (poison after too many attempts, or undecryptable) · skipped (nothing
-- new to land: every message already seen, or every object a duplicate).

alter table screen_session_deltas add column if not exists attempts integer not null default 0;
alter table screen_session_deltas add column if not exists claimed_by text;
alter table screen_session_deltas add column if not exists lease_until timestamptz;
alter table screen_session_deltas add column if not exists not_before timestamptz;
alter table screen_session_deltas add column if not exists promoted_at timestamptz;
alter table screen_session_deltas add column if not exists event_ids text[];
alter table screen_session_deltas add column if not exists last_error text;

alter table screen_session_deltas drop constraint if exists screen_session_deltas_status_ck;
alter table screen_session_deltas add constraint screen_session_deltas_status_ck
    check (status in ('held', 'promoted', 'deferred', 'parked', 'skipped'));

-- The promoter's claim scan: only open rows, so it stays small however long retention is.
create index if not exists screen_session_deltas_open
    on screen_session_deltas (org_id, received_at) where status in ('held', 'deferred');

-- L1.3.8 · Attachment Resolver — the refetch ladder, persisted.
--
-- WHY. `capture/parked/drain.py` already knows which parks are NEEDS_REFETCH (DOC-02/04/05/06)
-- and deliberately refuses to re-adjudicate them, because the retained payload for an attachment
-- stub is `body: ""` — the bytes never existed locally. It counted them and moved on, so a
-- contract whose download failed on first sync sat at `status='pending'` forever.
--
-- A refetch that is not bounded is worse than none: it re-downloads a permanently-deleted
-- attachment on every cycle, and "we retried it" stays true forever while the file never arrives.
-- So the ladder lives ON the park row: how many attempts it has cost, when the last one ran, when
-- the next one is allowed, and what the last failure said. Those four columns are what make the
-- G2 assertion — "0 attachments stuck in NEEDS_REFETCH over 1h" — a query rather than an opinion:
-- STUCK is `status='pending'` with `created_at` older than an hour, and its AGE is a column.
--
-- `status` gains one value, 'dead_letter': attempts exhausted, or a failure only a code change can
-- fix. A dead letter is a terminal state with a reason attached, which is the difference between
-- an attachment we gave up on and an attachment we quietly lost.
--
-- No new TABLE: parked_events is already in `_ORG_SCOPED_TABLES` in api/account_routes.py, so
-- tenant erasure keeps working unchanged. `document_jobs` gains `created_at` so the provenance
-- rows a recovery writes can be ordered against the ones ingestion wrote — without it, two rows
-- for one event have no defined "latest" and the S1 report cannot tell a recovered document from
-- the failure it replaced.

alter table parked_events add column if not exists refetch_attempts int not null default 0;
alter table parked_events add column if not exists refetch_first_attempt_at timestamptz;
alter table parked_events add column if not exists refetch_last_attempt_at timestamptz;
alter table parked_events add column if not exists refetch_next_attempt_at timestamptz;
alter table parked_events add column if not exists refetch_last_error text;

-- The claim query: pending parks whose backoff has elapsed, oldest first.
create index if not exists parked_events_refetch_due
    on parked_events (status, refetch_next_attempt_at, created_at);
-- The G2 metric and the admin console: this org's parks by reason and state, oldest first.
create index if not exists parked_events_org_reason_status
    on parked_events (org_id, reason_code, status, created_at);

alter table document_jobs add column if not exists created_at timestamptz not null default now();
create index if not exists document_jobs_by_event on document_jobs (org_id, event_id, created_at);

-- L1.3.8 · Attachment Resolver — record WHICH kind of failure ended a refetch.
--
-- WHY. `capture/parked/refetch_policy.py` already computes a failure KIND on every settlement —
-- `transient` (the network, a rate limit, a token mid-refresh), `permanent` (the provider says
-- the bytes are gone), `capability` (we hold the bytes and no engine here can read them) — and
-- its own docstring says why that distinction is load-bearing: "we could not read it" and "we
-- could not fetch it" have different fixes. The write then dropped it on the floor. Every dead
-- letter reached `parked_events` as a status plus a free-text `refetch_last_error`, so the admin
-- console (`GET /parked/refetch`) could show an operator a wall of provider prose and still not
-- answer the only question they have: is this queue full of files to go and LOOK at, or full of
-- files that are waiting on a parser we have not shipped?
--
-- A message is truncated, translated and provider-shaped. A kind is a value, and it is what makes
-- `POST /parked/refetch/requeue` a decision — you requeue the capability class the day an engine
-- lands, and you do not requeue the permanent one at all.
--
-- Nullable with no default and no backfill on purpose: rows written before this column existed
-- genuinely do not know their kind, and inventing one ("probably transient") would put a claim in
-- the database that no run ever made. They fill in on their next settlement.
--
-- No new TABLE, so tenant erasure (`_ORG_SCOPED_TABLES` in api/account_routes.py) is unchanged.

alter table parked_events add column if not exists refetch_failure_kind text;

-- The admin-console query: this org's dead letters, grouped by what stopped them.
create index if not exists parked_events_failure_kind
    on parked_events (org_id, status, refetch_failure_kind);

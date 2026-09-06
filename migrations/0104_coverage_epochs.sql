-- X6 · L2.5.5 typed absence + L-5 the coverage epoch — the two tables that make an absence
-- answerable and a negative inference revocable.
--
-- WHY AN EPOCH AT ALL (doc 13, loop L-5). L2.5.5 licenses a negative inference on
-- GENUINELY_ABSENT: "no support tickets, and the desk is connected, therefore this account is
-- healthy." Then the founder connects Intercom. Yesterday's absence was computed against a
-- source set that no longer exists, every inference drawn under it is now unverified, and
-- nothing in this schema could notice — a coverage row is an UPSERT, so the moment the sources
-- change the evidence that the old answer was ever true is overwritten in place.
--
-- `coverage_epochs` is the append-only half of `source_coverage`: one row per (org, domain,
-- epoch) with the window `[opened_at, closed_at)` over which one coverage answer held. That
-- window IS "the period over which coverage_ready was true for a source" — the thing a trend, a
-- gap and an absence all have to be able to ask about a PAST instant, and which an upserted
-- current-state row can only ever answer "now".
--
-- SCOPED PER DOMAIN, and that is the whole reason the fingerprint is not the raw row. Doc 13:
-- "a new billing connector does not invalidate support-absence inferences. The epoch check is
-- per-capability, or every connector change re-derives the whole graph." `source_coverage`
-- stores `connected` as the org's WHOLE capability set on every domain's row, so hashing the row
-- would bump all four domains whenever any connector moved. `epoch.fingerprint` hashes only the
-- capabilities the domain's own requirements name, so connecting Stripe moves `admin` and leaves
-- `sales` alone.
--
-- NOTHING IS EVER DELETED HERE. A superseded epoch is CLOSED, not removed, and an inference drawn
-- under it is MARKED stale rather than dropped: deleting it would lose the audit trail of what
-- the system believed and why, which is the only way to answer "why did we say that in March".

alter table source_coverage
    -- Doc 13's DDL line, verbatim in intent. The CURRENT epoch for this (org, domain), so the
    -- staleness check on a stored inference is one integer comparison against a row a reader
    -- already has, rather than a window query per absence.
    add column if not exists coverage_epoch bigint not null default 1;

create table if not exists coverage_epochs (
    -- The org cascade is on the CREATE, not a later ALTER, so `tests/test_account_erasure.py`'s
    -- replay sees it the moment the table exists. A tenant's coverage history is theirs.
    org_id          text not null references orgs (id) on delete cascade,
    domain          text not null,
    -- Monotonic per (org, domain), starting at 1. Never reused: an epoch number IS the identity
    -- of one coverage regime, and a reused number would silently re-validate the inferences the
    -- bump was raised to invalidate.
    epoch           bigint not null,
    -- What the answer WAS over this window. Stored, not joined: the point of the row is that
    -- `source_coverage.coverage_ready` has already moved on.
    coverage_ready  boolean not null,
    -- The content address of the domain-scoped capability state. Two sweeps that see the same
    -- sources produce the same fingerprint and no new epoch; a change of any kind produces a
    -- different one. Comparing fingerprints rather than timestamps is what makes the advance
    -- idempotent under a sweep that runs every ten minutes.
    fingerprint     text not null,
    -- The capability statuses the fingerprint was taken over, as `capability=status` pairs. The
    -- RECEIPT for the bump: without it "the epoch changed" is a claim with nothing behind it and
    -- no way to say WHICH connector moved.
    capabilities    text[] not null default '{}',
    opened_at       timestamptz not null,
    -- NULL means still open. Exactly one open epoch per (org, domain) — see the unique index.
    closed_at       timestamptz,
    primary key (org_id, domain, epoch),
    -- A window that ends before it starts would make `epoch_at` answer two epochs for one
    -- instant, and the caller would take whichever the planner returned first.
    constraint coverage_epochs_window_ordered check (closed_at is null or closed_at > opened_at)
);

-- ONE open epoch per (org, domain). Two would mean an instant belongs to two coverage regimes,
-- and the tri-state read below would have to pick — which is the same as guessing.
create unique index if not exists coverage_epochs_one_open
    on coverage_epochs (org_id, domain) where closed_at is null;

create index if not exists coverage_epochs_lookup
    on coverage_epochs (org_id, domain, opened_at desc);


-- L2.5.5-U1 · the typed absences themselves. One row per (situation, expected fact) that is NOT
-- present, carrying WHICH KIND of not-present it is.
--
-- WHY A TABLE AND NOT A JSONB COLUMN ON `context_situations`. `context_situations.missing`
-- already holds the plain-language labels, and that column is the defect this table exists to
-- fix: a label ("deal value") cannot be joined, cannot be queried by type, has no coverage basis
-- and cannot carry the epoch it was drawn under. The H6 gate row is a COUNT — "0 negative
-- inferences drawn from UNKNOWABLE facts" — and a count over a jsonb array of human phrases is
-- not a measurement.
create table if not exists situation_absences (
    org_id          text not null references orgs (id) on delete cascade,
    situation_id    text not null,
    -- The expectation's own key: a field PATH (`deal.value`), never the human label. The labels
    -- have spaces, match nothing in the graph, and cannot be consulted by
    -- `packs/compiler/context_adapter.evaluate` — which is how an `exists:` test on a field
    -- nothing ever wrote came back a confident FALSE.
    expected_fact   text not null,
    subject_node_id text not null,
    -- One of `AbsenceType`. `present` is never stored — a row here IS an absence — but the enum
    -- is not narrowed in the constraint, so a future member does not need a migration to be
    -- readable.
    absence_type    text not null,
    -- Tri-state, and NULL IS NOT FALSE: an unassessed domain is unknowable, never absent.
    coverage_ready  boolean,
    -- WHAT WE LOOKED AT. The receipt for "we looked and it was not there".
    coverage_basis  text[] not null default '{}',
    coverage_domain text not null,
    -- The epoch this absence was concluded under. THE REVOCATION KEY: an absence whose epoch is
    -- behind its domain's current epoch was drawn against a source set that no longer exists.
    coverage_epoch  bigint,
    -- COMPUTED, mirrored from the contract so a SQL reader gets the same answer a Python reader
    -- does. The check constraint below is what stops the two from disagreeing.
    licenses_negative_inference boolean not null,
    computed_at     timestamptz not null,
    primary key (org_id, situation_id, expected_fact),

    -- THE THREE DOCTRINE CONSTRAINTS. `contracts/quality.MissingFact` enforces all three in
    -- Python; they are restated here because a table is reachable by six writers and a
    -- constraint that lives only in one of them is a convention, not a rule.
    --
    -- 1. the licence is the type, and nothing else.
    constraint situation_absences_licence_is_computed
        check (licenses_negative_inference = (absence_type = 'genuinely_absent')),
    -- 2. coverage_ready is checked FIRST, always: absent requires a source that could have
    --    carried it. `is true` and NOT a bare `coverage_ready`, because a CHECK that evaluates
    --    to NULL is SATISFIED in Postgres — so the bare spelling admits exactly the row this
    --    constraint exists to refuse, the one where coverage was never assessed and the absence
    --    was licensed anyway. `is true` is three-valued-safe and NULL fails it.
    constraint situation_absences_absent_needs_coverage
        check (absence_type <> 'genuinely_absent' or coverage_ready is true),
    -- 3. no claim without a receipt: the strongest thing this table can say must name what was
    --    searched.
    constraint situation_absences_absent_needs_basis
        check (absence_type <> 'genuinely_absent'
               or coalesce(array_length(coverage_basis, 1), 0) > 0)
);

create index if not exists situation_absences_by_type
    on situation_absences (org_id, absence_type);

create index if not exists situation_absences_findings
    on situation_absences (org_id, coverage_domain)
    where licenses_negative_inference;

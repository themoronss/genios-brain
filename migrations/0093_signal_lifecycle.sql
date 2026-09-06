-- L1.6.9-U1 (ALG-19) · the signal LIFECYCLE row. One table, one idea:
-- **a signal is not a fact frozen at capture** — it is superseded, it expires, or it is resolved.
--
-- THE DEFECT THIS CLOSES. `qualified_signals.state` (doc 08) defaults to 'active' and nothing in
-- capture ever wrote a second value into it, so every signal this system ever emitted stood live
-- for ever. Doc 06 names the cost: *"a renewal signal about a contract that was cancelled is dead,
-- and must be marked so"* — otherwise L2 correlates a ghost and the founder is nudged about
-- something that resolved last week. Globe Rule 08, stale beats wrong, applied at L1.
--
-- WHY A ROW PER SIGNAL AND NOT A COLUMN ON THE SIGNAL. Supersession is a decision about a signal
-- captured LAST MONTH, and last month's `QualifiedEnterpriseSignal` — 24 fields with the whole
-- extraction embedded — is not in memory during today's sweep. This table carries exactly the
-- eight facts the state machine needs, so "what already stands for this subject" is one indexed
-- read instead of a page of rehydrated payloads.
--
-- DIRECTION OF `supersedes`, decided in `capture/esqe/lifecycle.py` and stated once: it points
-- BACKWARD, from the newer signal to the one it replaced. C-12 asked L1.6.9 to pick, and backward
-- is the only direction that can express doc 06's revive rule — *"revive creates a new signal id
-- and does not mutate the expired row"* — because a forward pointer would have to be written into
-- the expired row to record the revival, which is the mutation the rule forbids.
--
-- ORG CASCADE. `tests/test_account_erasure.py` replays every migration statically and fails any
-- table with an `org_id` that cannot be erased with its tenant. `subject_key` is ALG-22's derived
-- subject and carries the tenant's own counterparties and deal names, so this is not a formality.
-- The table is also listed in `api/account_routes._ORG_SCOPED_TABLES`, which is what makes /reset
-- erase it as well as account deletion.

create table if not exists signal_lifecycle (
    org_id         text not null references orgs (id) on delete cascade,
    signal_id      text not null,
    -- ALG-22's subject + the signal type ARE the supersession key. Both, never either: a renewal
    -- does not supersede a decision about the same customer, and conflating them is how a live
    -- open loop silently disappears.
    subject_key    text not null,
    signal_type    text not null,
    -- ALG-14's 0..6 artifact ladder, copied onto the row on purpose (the same argument
    -- `ConflictClaim.authority_rank` makes): a supersession must keep explaining the decision it
    -- actually made even after the authority table is re-tuned.
    authority_rank integer not null,
    -- WORLD time. Ordering is by this and never by ingest order, or a backfilled thread from
    -- March supersedes this morning's contract because it was swept second.
    occurred_at    timestamptz not null,
    state          text not null default 'active',
    supersedes     text,
    expires_at     timestamptz,
    -- The `eval_time` this state was decided against — never a clock read inside the engine. It
    -- is what makes a lifecycle decision replayable: the same sweep at the same instant must
    -- produce the same states in September as it did in March.
    evaluated_at   timestamptz not null,
    primary key (org_id, signal_id),
    constraint signal_lifecycle_state_closed
        check (state in ('active', 'superseded', 'expired', 'resolved')),
    constraint signal_lifecycle_rank_range check (authority_rank between 0 and 6),
    -- A state that names no clock cannot be explained or replayed: ALG-19 expires ON `expires_at`,
    -- so an 'expired' row without one is a claim that a clock ran out while naming no clock.
    constraint signal_lifecycle_expired_has_clock
        check (state <> 'expired' or expires_at is not null),
    -- `supersedes` is walked to find what is current; a self-pointer is a one-node cycle.
    constraint signal_lifecycle_no_self_supersede check (supersedes is distinct from signal_id)
);

-- "What is currently live for this subject" — the sweep's own read, and the only one on the hot
-- path. Partial on `active` because the three terminal states are history and are never scanned
-- to decide a supersession.
create index if not exists signal_lifecycle_open_by_subject
    on signal_lifecycle (org_id, subject_key, signal_type, occurred_at)
    where state = 'active';
-- "Show me this chain" — the audit read, backwards along the pointer.
create index if not exists signal_lifecycle_by_supersedes
    on signal_lifecycle (org_id, supersedes) where supersedes is not null;

comment on table signal_lifecycle is
  'L1.6.9 (ALG-19) signal lifecycle: one row per signal carrying state / supersedes / expires_at, written by capture/esqe/lifecycle.py from api/routes._run_ledger. Erased with the tenant (org cascade + api/account_routes._ORG_SCOPED_TABLES).';
comment on column signal_lifecycle.supersedes is
  'BACKWARD pointer: the signal_id THIS row replaced. Set once at insert on the newer row; the older row is marked state=superseded and is never rewritten again. See the direction argument in capture/esqe/lifecycle.py.';
comment on column signal_lifecycle.expires_at is
  'ALG-19 default by type, computed from the signal OWN dates: commitment_due / deadline_stated / contract_renewal = the stated date + 30d, decision_pending = 90d, others = 180d, measured from occurred_at when the source stated no date.';

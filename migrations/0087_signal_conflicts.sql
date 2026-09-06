-- L1.5.5-U1 · `signal_conflicts` — the conflict store. DDL from doc 05 (L1.5.5-U1), verbatim in
-- its column set, plus the two things a table in THIS database cannot ship without.
--
-- THE DEFECT THIS CLOSES. ALG-12 runs in production today: `sync_runner._detect_conflicts`
-- compares every claim a sweep extracted and returns a `ConflictOutcome` on the `SyncSummary`.
-- Nothing persisted it. `contracts/conflict.py` states of a `ConflictClaim` — *"Both of them are
-- written to signal_conflicts.claims and neither is ever pruned"* — about a table that did not
-- exist, so doc 05's design law ("the conflict record ALWAYS retains both sides") held for
-- exactly as long as the Python object lived. A disagreement between a signed PDF and the email
-- that quotes it was computed, rendered into an escalation, and then forgotten; asking "what did
-- we know was contested last month" had no answer at all.
--
-- WHY PERMANENT (doc 07's storage map says so, and the reason is not sentiment): the losing
-- claim is the evidence that the winner was contested. A card that shows only the resolved value
-- cannot explain itself, and the founder may know something the authority ranking does not.
-- The only deletion is the tenant's own — see the cascade below.
--
-- TWO ADDITIONS TO THE DOC'S DDL, both required by this codebase rather than by the plan:
--
--   org cascade — every org-scoped table in this database carries
--                 `references orgs (id) on delete cascade`, and `tests/test_account_erasure.py`
--                 replays every migration statically and FAILS any table with an `org_id` that
--                 does not. Without it a deleted customer's contract amounts and quoted
--                 sentences would outlive their account. `not valid` for the same reason 0080
--                 uses it: the constraint binds new rows immediately without a full-table
--                 validation scan on a live database.
--   event_ids   — which events the two competing claims came from. `DetectedConflict` carries
--                 it (`capture/validate/conflict.py`), the doc's DDL has nowhere to put it, and
--                 without it a stored conflict cannot be traced back to the two messages that
--                 disagreed — which is the first thing anyone re-judging one asks. jsonb rather
--                 than text[] to match `claims` and to keep the whole row one serializer.
--
-- `signal_id` is the doc's column and it is NOT NULL there. The qualified-signal store (L1.7.4)
-- is a later wave, so today the writer files the event that carried the STRONGEST claim — the
-- first entry of `event_ids`, which is exactly what a reader needs to find the conflict from a
-- message. When the signal store lands, that writer changes and these rows stay readable,
-- because the column has always meant "the thing this conflict is about".
create table if not exists signal_conflicts (
    conflict_id    text primary key,
    org_id         text not null references orgs (id) on delete cascade,
    signal_id      text not null,
    field          text not null,
    subject_key    text not null,
    claims         jsonb not null,        -- full ConflictClaim list, both sides
    resolution     text not null,
    resolved_value jsonb,
    event_ids      jsonb not null default '[]'::jsonb,
    detected_at    timestamptz not null default now()
);

-- Doc 05's index, verbatim: "which conflicts is this signal carrying" is the read every card
-- render and every re-judgement performs.
create index if not exists conflicts_by_signal on signal_conflicts (org_id, signal_id);

-- The resolution vocabulary is closed — `ConflictResolution` has exactly three members and there
-- is deliberately no free-text reason field beside it — so the database enforces it. A row
-- claiming 'resolved_by_recency_v2' is a detector bug, and the insert is the cheapest place to
-- learn that.
do $$
begin
    if not exists (select 1 from pg_constraint
                    where conrelid = 'public.signal_conflicts'::regclass
                      and conname = 'signal_conflicts_resolution_check') then
        alter table signal_conflicts add constraint signal_conflicts_resolution_check
            check (resolution in ('unresolved_surface_both', 'resolved_by_authority',
                                  'resolved_by_recency'));
    end if;
end
$$;

comment on table signal_conflicts is
  'L1.5.5 (ALG-12) conflict store: one row per detected disagreement, BOTH sides retained permanently. Written by capture/validate/conflict_store.py from a sweeps ConflictOutcome; erased only with the tenant (org cascade + api/account_routes._ORG_SCOPED_TABLES).';
comment on column signal_conflicts.conflict_id is
  'sha256 over org_id : signal_id : subject_key : field : resolution : claims : resolved_value. Content-addressed so a replayed sweep upserts its own row instead of appending a second copy of the same disagreement; detected_at is deliberately NOT in the digest.';
comment on column signal_conflicts.claims is
  'The full ConflictClaim list, both sides, never pruned. The losing claim is the evidence that the winner was contested.';
comment on column signal_conflicts.event_ids is
  'The events the competing claims came from, strongest claim first. Two distinct ids is what proves a cross-event conflict rather than one event contradicting itself.';

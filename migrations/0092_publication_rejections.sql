-- L1.6.10 · the REJECTION LEDGER, and the closed 14 enforced by the database.
--
-- THE DEFECT THIS CLOSES. `contracts/publication.py` has seven rules and only two of them left
-- a trace. V-1 parks (a reviewable `parked_events` row) and the qualification floor drops (a
-- `qualification_drops` row); V-2, V-3, V-4, V-6 and V-7 REJECT — and the publisher built a
-- `RefusedSignal`, returned it on a report nobody stored, and discarded it. So a signal refused
-- for a kind outside the taxonomy, an out-of-range importance, a claim with no receipt or a
-- Rule 11 violation vanished with no record at all, and *"why did I never see X?"* — the whole
-- justification for keeping a refusal — had an answer for two of the seven rules and silence
-- for five.
--
-- WHY THIS IS A SIBLING TABLE AND NOT MORE ROWS IN `qualification_drops`. It is built on that
-- table's own terms — a content-addressed id so a replayed sweep upserts instead of appending,
-- the payload ref that makes the refusal RECONSTRUCTABLE, the same 90-day retention promise
-- extended on `raw_payloads` in the same transaction, the same two indexes, the same org
-- cascade — and it is deliberately not the same table, for a reason the DDL itself states:
--
--     constraint qualification_drops_below_floor check (importance_bp < floor_bp)
--
-- A drop IS the comparison of a score against a floor. A V-2 rejection has no floor in it and
-- frequently no usable score either (V-3's whole failure mode is an importance that is not
-- basis points), so writing one into that table would mean inventing a `floor_bp` large enough
-- to satisfy a CHECK — a fabricated number, in a permanent record, to make an unrelated
-- invariant hold. Two ledgers with one shape is honest; one ledger with a lie in it is not.
--
-- `signal_type` HERE IS DELIBERATELY UNCONSTRAINED, which is the exact opposite of the two
-- ALTERs below and for the exact same reason: V-2's failure IS a kind outside the closed 14, so
-- a ledger that could not store the offending value would be unable to record the one rejection
-- most in need of a record. The constrained tables hold what we BELIEVE; this one holds what we
-- REFUSED, and a refusal must be able to quote the thing it refused.
create table if not exists publication_rejections (
    rejection_id  text primary key,
    org_id        text not null references orgs (id) on delete cascade,
    signal_id     text not null,
    event_id      text not null,
    -- The kind as the refused object carried it. See above: not constrained, on purpose.
    signal_type   text not null default '',
    -- `reject` (a V-rule refused it) or `unbuildable` (the contract's own constructor refused it
    -- for something outside V-1..V-7, so the gate cannot name a rule). Two different bugs to go
    -- fix, and a ledger that blurred them would send every investigation to the wrong place.
    outcome       text not null,
    -- Every BLOCKING rule that failed, as the ids the V-table is cited by ('["V-4","V-6"]').
    -- All of them, not the first: a signal that breaks two rules has two upstream bugs, and
    -- fixing them one release apart is how a pipeline stays broken for three releases.
    rules         jsonb not null default '[]'::jsonb,
    -- The sentence a reviewer needs, joined across the failures. Stored rather than re-derived:
    -- by the time anyone reads it the signal object is gone and so is the stack that produced it.
    reason        text not null default '',
    -- `prepared_content:<id>` or `raw_payload:<event_id>` — the same `prefix:id` provenance form
    -- ALG-14 matches on, so the refused signal is reconstructable and not merely regrettable.
    payload_ref   text,
    evaluated_at  timestamptz not null,
    retain_until  timestamptz not null,
    constraint publication_rejections_outcome check (outcome in ('reject', 'unbuildable')),
    constraint publication_rejections_rules_array check (jsonb_typeof(rules) = 'array')
);

-- "What did this tenant not see, most recently first" — the same read `qualification_drops`
-- is indexed for, because it is the same question asked about the other half of the gate.
create index if not exists publication_rejections_by_org
    on publication_rejections (org_id, evaluated_at desc);
-- "Why did this event produce nothing" — answered from the event id a founder can name.
create index if not exists publication_rejections_by_event
    on publication_rejections (org_id, event_id);

comment on table publication_rejections is
  'L1.6.10 rejection ledger: one row per signal the publication gate REFUSED (V-2/V-3/V-4/V-6/V-7, plus the fail-closed `unbuildable` case), carrying every broken rule, the reason and a payload ref so the refusal is reconstructable. Written by capture/esqe/publisher.py; erased with the tenant (org cascade + api/account_routes._ORG_SCOPED_TABLES).';
comment on column publication_rejections.rejection_id is
  'sha256 over org_id : signal_id : outcome : the blocking rule ids. Content-addressed so a replayed sweep upserts its own row instead of appending a second copy of one refusal; evaluated_at is deliberately NOT in the digest.';
comment on column publication_rejections.signal_type is
  'The kind the refused object carried — intentionally NOT constrained to the closed 14, because V-2 rejects a kind that is not in it and the ledger has to be able to quote the offending value.';


-- ── THE CLOSED 14, ENFORCED BY THE DATABASE ────────────────────────────────────────────────
--
-- `contracts/signal.SignalType` is a closed 14-member taxonomy and it was closed only in Python.
-- Both tables below are read by every downstream surface, and both are reachable by writers that
-- never pass through the contract — a backfill script, a psql session, a future ingestion path,
-- an `on conflict do update` from a build one schema version behind. A fifteenth kind landing in
-- either one is silent: ALG-16 has no precedence for it and ALG-17 has no weight for it, so it
-- classifies as nothing in particular and scores as nothing in particular, for ever, with no
-- error anywhere. A CHECK is what makes "closed" mean closed.
--
-- Guarded on `pg_constraint` rather than written as a bare ADD: `alter table ... add constraint`
-- has no `if not exists`, and a migration that cannot be re-read on a database somebody has
-- already patched by hand is a migration that fails on exactly one machine.
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'qualified_signals_signal_type') then
        alter table qualified_signals add constraint qualified_signals_signal_type check (
            signal_type in ('commitment_made', 'commitment_due', 'deadline_stated',
                            'decision_pending', 'decision_made', 'approval_requested',
                            'escalation', 'risk_flagged', 'opportunity_signal',
                            'relationship_change', 'financial_obligation', 'contract_renewal',
                            'anomaly', 'information_conflict'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'qualification_drops_signal_type') then
        alter table qualification_drops add constraint qualification_drops_signal_type check (
            signal_type in ('commitment_made', 'commitment_due', 'deadline_stated',
                            'decision_pending', 'decision_made', 'approval_requested',
                            'escalation', 'risk_flagged', 'opportunity_signal',
                            'relationship_change', 'financial_obligation', 'contract_renewal',
                            'anomaly', 'information_conflict'));
    end if;
end $$;


-- ── `authority_rank` · ALG-14 -> the legacy scale, translated ONCE, at the write ────────────
--
-- `capture/validate/authority.to_legacy_rank` is the module's own stated "one sanctioned
-- crossing" between ALG-14's 0..6 ladder and the 0..4 scale `context.pipeline.FACT_CONF_BY_RANK`
-- is keyed by, and it had no caller outside its test. The two scales share the digits 0..4 and
-- mean different things by them (legacy 4 = company canon, ALG-14 4 = a structured source of
-- record), so a consumer that re-derives the translation gets it wrong for four of the seven
-- classes — usually as `rank - 1` — and silently demotes a signed contract to a CRM row.
--
-- The crossing therefore belongs at the WRITE, which is this table: the publisher translates
-- once, from the authority ALG-14 already computed on the signal's attribution, and every reader
-- of `qualified_signals` gets a number that is a live key of `FACT_CONF_BY_RANK` instead of a
-- ladder position it has to re-base. Nullable, because a row written before this column existed
-- has no honest answer and a default would invent one.
alter table qualified_signals add column if not exists authority_rank smallint;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'qualified_signals_authority_rank') then
        alter table qualified_signals add constraint qualified_signals_authority_rank
            check (authority_rank is null or authority_rank between 1 and 4);
    end if;
end $$;

comment on column qualified_signals.authority_rank is
  'ALG-14 authority translated to the 0..4 scale context.pipeline.FACT_CONF_BY_RANK is keyed by, via capture/validate/authority.to_legacy_rank. Written at publish so the crossing happens once; null on rows written before migration 0092.';

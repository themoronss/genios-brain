-- L1.6.10-U2 / L1.7.4 · `qualified_signals` — the L1 -> L2 boundary, made durable.
--
-- WHY THIS TABLE EXISTS. `source_events` is a landing ledger: it records that an object was
-- INGESTED, not that a business signal was found in it. `qualification_drops` (0088) records
-- what the floor REFUSED. Between them sat the one thing nobody stored — what Layer 1 actually
-- concluded. L2 had no durable set of signals to read, re-read, or replay against, so every
-- answer to "what does the engine believe about this tenant right now" had to be recomputed by
-- re-running capture over mail we had already paid to read.
--
-- ONE ROW PER `QualifiedEnterpriseSignal`, written by `capture/esqe/publisher.py` AFTER
-- `contracts/publication.validate_publication` returned EMIT. A signal that parked (V-1) leaves
-- a `parked_events` row instead; a signal that was rejected (V-2..V-4, V-6, V-7) leaves no row
-- here at all, which is the point of the gate.
--
-- `confidence_bp` IS THE PUBLISHED VALUE, NOT THE COMPOSED ONE. V-5 downgrades an unverified
-- signal and emits it; the publisher stores `decision.signal`, so this column carries the
-- REDUCED number. Storing the composer's original here would silently re-inflate a confidence
-- the gate had just reduced, in the one place a human reads it back.
--
-- `extraction_ref` is a POINTER into `l1_extraction_results.processing_key`, never a copy. The
-- extraction lives once — it is the expensive artifact and it is content-addressed — and a
-- second copy of it per signal would multiply the largest rows in the database by the number of
-- signals each email produced. Structured-lane events use the `struct:<event_id>` form that
-- `context/runner.py` and `context/pipeline.py` already file them under, so the pointer resolves
-- for both lanes.
--
-- `importance_components` is stored ALONGSIDE `importance_bp`, and `importance_version` beside
-- both. "Why is this an 8100?" must be answerable from data, without recomputation, and it must
-- stay answerable after the weights move: a re-tuned ALG-17 must not silently re-explain a score
-- that was made under the old ones. This is `qualification_drops.components`' rule applied to
-- the half of the distribution that DID cross.
--
-- `envelope` IS A DELIBERATE ADDITION to the DDL printed in doc 06 (L1.6.10-U2), and the reason
-- is doc 07's own stated purpose for this table: a set L2 can "read, re-read, or REPLAY
-- against". The printed columns cannot rebuild a C-12 — they carry no `source`, `object_type`,
-- `triage_lane`, `recipients`, `versions` or `schema_version` — so a replay would have to join
-- `source_events` and then guess at the version map that produced the row, which is the exact
-- thing `versions` exists to prevent. One jsonb column holding those six keys makes the row
-- round-trippable. It adds a column; it renames and drops nothing, so every query the doc's DDL
-- supports is unaffected.
--
-- ERASURE. The org FK cascades on account deletion. `qualified_signals` is ALSO listed in
-- `api/account_routes.py::_ORG_SCOPED_TABLES`, which is what makes /reset erase it — that list
-- executes with no try/except by design, so a table missing from it leaks a deleted tenant's
-- quoted sentences (`evidence_refs` holds verbatim quotes) rather than failing loudly.
create table if not exists qualified_signals (
    signal_id             text primary key,
    org_id                text not null references orgs (id) on delete cascade,
    event_id              text not null,
    trace_id              text not null,
    signal_type           text not null,
    secondary_types       jsonb not null default '[]'::jsonb,
    importance_bp         integer not null,
    importance_components jsonb not null default '{}'::jsonb,
    importance_version    text not null,
    confidence_bp         integer not null,
    confidence_vector     jsonb not null default '{}'::jsonb,
    domain_hints          jsonb not null default '[]'::jsonb,
    visibility            jsonb not null,
    coverage_ready        boolean,
    extraction_ref        text not null,
    evidence_refs         jsonb not null,
    conflict_ids          jsonb not null default '[]'::jsonb,
    state                 text not null default 'active',
    supersedes            text,
    expires_at            timestamptz,
    internal_kind         text,
    occurred_at           timestamptz not null,
    envelope              jsonb not null default '{}'::jsonb,
    created_at            timestamptz not null default now(),
    -- V-3 and V-4 as storage constraints, not as a second copy of the gate. The publisher is
    -- the only writer and it runs the real validator; these two exist so a future writer that
    -- skipped the gate cannot land a row the gate would have refused.
    constraint qualified_signals_importance_bp check (importance_bp between 0 and 10000),
    constraint qualified_signals_confidence_bp check (confidence_bp between 0 and 10000),
    constraint qualified_signals_has_evidence check (jsonb_array_length(evidence_refs) > 0),
    -- A signal may not supersede itself: the one direction-independent invariant C-12 states
    -- while doc 06 and C-12 still disagree about which way the pointer runs.
    constraint qualified_signals_no_self_supersede check (supersedes is null or supersedes <> signal_id)
);

-- The ranked read L2 and every downstream surface actually performs: this tenant's live
-- signals, biggest first. `state` is in the key because `active` is the only state L2
-- correlates and the other three must not cost the scan.
create index if not exists qs_by_org_state on qualified_signals (org_id, state, importance_bp desc);
-- "Explain this card backwards" — the join from a signal to the event trace that produced it.
create index if not exists qs_by_trace on qualified_signals (org_id, trace_id);
-- "What did this event produce?" — the support question, asked from an event id a founder can
-- name, and the reverse of `qualification_drops_by_event`.
create index if not exists qs_by_event on qualified_signals (org_id, event_id);

comment on table qualified_signals is
  'L1.7.4 signal store: one row per QualifiedEnterpriseSignal that passed the L1.6.10 publication gate (V-1..V-7). Written by capture/esqe/publisher.py; erased with the tenant (org cascade + api/account_routes._ORG_SCOPED_TABLES).';
comment on column qualified_signals.confidence_bp is
  'The PUBLISHED confidence, after any V-5 downgrade for unverified evidence spans. Not the composer''s original.';
comment on column qualified_signals.extraction_ref is
  'Pointer into l1_extraction_results.processing_key (or struct:<event_id> for the structured lane). The extraction lives once and is never copied here.';
comment on column qualified_signals.importance_components is
  'The importance_components map exactly as L1.6.7 produced it. Stored, never recomputed: a weight change must not re-explain an old score.';
comment on column qualified_signals.envelope is
  'Round-trip envelope for replay: source, object_type, triage_lane, recipients, versions, schema_version. An addition to doc 06''s printed DDL — without it a stored row cannot rebuild the C-12 it came from.';

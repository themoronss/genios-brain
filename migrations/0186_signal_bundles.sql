-- 0186 · the signal bundle — the signals that arrived TOGETHER, stored as one thing.
--
-- WHAT WAS WRONG. Four signals about one vendor renewal crossed the L1 → L2 seam as four loose
-- events, and Layer 2 rebuilt the grouping from whatever survived the projection. Four weak
-- situations instead of one strong one. The grouping was knowable at capture, where the evidence
-- for it still existed, and was thrown away at the boundary — the `not_carried` class again, one
-- seam earlier than usual.
--
-- ⛔ THE PRIMARY KEY IS THE IDEMPOTENCE. `bundle_id` is derived from the signals it groups, so a
-- replayed connector page produces the SAME id and `on conflict do nothing` collapses it to one
-- row. A serial id would have made every replay a second bundle, and every denominator computed
-- from bundles wrong by however many times the page was retried. `QualifiedEnterpriseSignalBundle`
-- refuses a repeated signal id for the same reason at the other end of the same rule.
--
-- ⛔ AND THERE IS DELIBERATELY NO `completeness_bp` COLUMN. Coverage lives in jsonb, PER SOURCE, in
-- the shape `SignalCoverage.as_dict()` already writes on C-12:
--
--     "a tenant with complete calendar coverage and 8% email coverage has two different licences
--      to make a negative claim, and one blended number would grant the stronger one to both."
--
-- A single column here would be exactly that blended number, and a column is harder to refuse than
-- a field: the contract's validator can reject one at construction, but anything holding a
-- connection could write one. So the schema does not offer the shape. An unknown denominator stays
-- `null` inside the jsonb — never zero, never 10000.
--
-- WHAT IS NOT HERE, AND IS NOT AN OVERSIGHT. No `situation_id`, no `correlation_id`, no node
-- reference. This table holds what ARRIVED together, not what it means. Relating a bundle to what
-- the company already knows needs the graph, the graph is Layer 3, and `capture/` reading it is an
-- upward import that `tests/test_layer_topology.py` fails the build on. See `docs/LAYER_MAP.md`.

create table if not exists signal_bundles (
    --: Deterministic over (org, the sorted signal ids). Replay-safe by construction.
    bundle_id               text primary key,
    org_id                  text        not null,
    --: Minted in L1 and unchanged to L6, so a bundle is findable from any downstream receipt.
    trace_id                text        not null,
    --: What the group is ABOUT, when the grouper could name it. NULL is honest: a group can be
    --: real ("these three arrived in one thread") before anybody can say which object it concerns.
    subject_key             text,
    --: The members, in qualification order. jsonb rather than a join table because a bundle is
    --: written once and never edited — a child table would add a write, a read and a delete path
    --: for a value that has no lifecycle of its own.
    signal_ids              jsonb       not null,
    entity_keys             jsonb       not null default '[]'::jsonb,
    --: CANDIDATE, never asserted. "SIG-101 concerns CTR-441" is a proposal the grouper makes from
    --: what arrived together; Layer 2 may accept or discard it.
    candidate_relationships jsonb       not null default '[]'::jsonb,
    --: `SignalCoverage.as_dict()` — window_from, window_to, and one entry per source.
    coverage                jsonb       not null default '{}'::jsonb,
    --: What the grouper knows it could not settle. Layer 2 reads it to decide whether to ASK
    --: (an EvidenceNeed) rather than to guess.
    unresolved              jsonb       not null default '[]'::jsonb,
    created_at              timestamptz not null default now()
);

-- A bundle is only ever read for one tenant, newest first — the sweep's own access pattern.
create index if not exists signal_bundles_org_created_idx
    on signal_bundles (org_id, created_at desc);

-- Doc 07: "Every new table in this plan must be added to the existing 0033_org_data_cascade.sql
-- pattern. A table that survives a tenant deletion is a compliance defect, and it is the kind that
-- is only discovered during an audit." `tests/test_account_erasure.py` enforces it for every table
-- carrying `org_id`, so this is a build failure rather than a review nit.
alter table signal_bundles drop constraint if exists signal_bundles_org_cascade_fk;
alter table signal_bundles add constraint signal_bundles_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table signal_bundles is
  'L1 -> L2: signals that ARRIVED together, with the per-source coverage that licenses a negative '
  'claim about the group. Never a blended completeness figure; never a graph reference.';

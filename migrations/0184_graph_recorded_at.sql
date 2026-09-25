-- 0184 · L3-04 · KNOWLEDGE TIME — when we LEARNED a thing, as distinct from when it happened.
--
-- THE DEFECT. `GET /graph/as-of` says in its own docstring that it answers *"what did GeniOS know
-- when it made that decision?"* — the question doc 02 says every enterprise security review asks.
-- It answers it with one predicate applied to three tables:
--
--     valid_from <= :t and (valid_to is null or valid_to > :t)
--
-- and the three tables do not agree about what `valid_from` means.
--
--     graph_nodes    valid_from = now()        (the column default; no writer overrides it)
--     graph_facts    valid_from = now()        (same)
--     graph_edges    valid_from = coalesce(occurred_at, now())   ⛔ THE EVENT'S OWN TIME
--
-- `write_edge` binds `:vf` to `occurred_at`, and on the live capture path that is the message
-- timestamp (`context/pipeline.py:1040`, `context/structured.py:95`, `context/documents.py:267`).
--
-- WHAT THAT PRODUCES. Backfill a six-month-old email today and the edge it creates is stamped six
-- months ago. An as-of read of five months ago then SEES a relationship we learned about this
-- morning — which is LCX-02 and CL-02 exactly: *"history is rewritten to make the system appear to
-- have known the correction earlier than it did."* The `historical` empty-window trick in
-- `write_fact` protects facts from precisely this and there is no equivalent on edges.
--
-- ⛔ AND L3-0A MAKES IT WORSE ON PURPOSE. That step exists to widen the backfill window from 60
-- days towards 365, because five of the benchmark's eight waiting relationships sit outside 60.
-- Every one of those is a year of edges backdated into the as-of history.
--
-- WHY THE COLUMN IS NOT SIMPLY REDEFINED. `graph_edges.valid_from` has a second set of readers who
-- are right to read it as event time: `reason/moments/recall.py` takes `max(valid_from)` as "when
-- did we last relate to this node", and `reason/moments/slice.py` orders by it. Changing the write
-- to `now()` would silently move every one of those answers to "when did we last hear about it",
-- which is a different question with the same shape — the worst kind of change, because nothing
-- would fail. So the meaning is not taken away from anyone; a second, unambiguous one is added.
--
-- NULLABLE, WITH NO BACKFILL, AND THAT IS THE POINT. `add column ... default now()` would stamp
-- every existing row with the migration's own instant and assert that we learned a tenant's entire
-- history at 03:00 on the night this deployed. `add column ... default valid_from` would assert
-- the very thing this migration exists to stop believing. WE DO NOT KNOW WHEN WE LEARNED THE
-- EXISTING ROWS, and a value we cannot reconstruct must not be fabricated — the same rule that
-- makes `claimed_total` null rather than zero and `completeness_bp` None rather than 10000.
--
-- The reader therefore uses `coalesce(recorded_at, valid_from)`: new rows get the honest answer,
-- pre-migration rows keep exactly the behaviour they have today. Nodes and facts are unaffected
-- either way, because for them `valid_from` already IS the write time — the coalesce is uniform so
-- that one predicate keeps spanning three tables, which is the property `_view` was built on.
--
-- Idempotent: add-if-not-exists throughout, safe to re-run.

alter table graph_nodes  add column if not exists recorded_at timestamptz;
alter table graph_facts  add column if not exists recorded_at timestamptz;
alter table graph_edges  add column if not exists recorded_at timestamptz;

comment on column graph_nodes.recorded_at is
    'When GeniOS learned this version, as distinct from when it became true. NULL on rows written '
    'before 0184: unreconstructable, and not fabricated. Readers use coalesce(recorded_at, '
    'valid_from).';
comment on column graph_facts.recorded_at is
    'When GeniOS learned this version. See graph_nodes.recorded_at.';
comment on column graph_edges.recorded_at is
    'When GeniOS learned this edge. ⛔ NOT valid_from, which on this table carries the EVENT time '
    '(coalesce(occurred_at, now())) and has readers in reason/moments that depend on it.';

-- "What did we know at T" is the audit question, so it is an index scan rather than a scan of
-- every version ever written. Partial on `recorded_at is not null` because pre-migration rows
-- cannot answer it and an index over their nulls would be dead weight on the largest part of the
-- table for as long as the oldest tenant lives.
create index if not exists graph_nodes_recorded_at
    on graph_nodes (org_id, recorded_at) where recorded_at is not null;
create index if not exists graph_facts_recorded_at
    on graph_facts (org_id, recorded_at) where recorded_at is not null;
create index if not exists graph_edges_recorded_at
    on graph_edges (org_id, recorded_at) where recorded_at is not null;

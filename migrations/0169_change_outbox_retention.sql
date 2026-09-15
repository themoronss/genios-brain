-- L2 · the graph change outbox gets a horizon, and an index that serves its reader.
--
-- WHAT THIS TABLE IS AND IS NOT. `graph_change_outbox` takes one row per committed event — both
-- lanes write it, `pipeline.py` and `structured.py` — carrying the graph version that event
-- reached and five integer counts. It has a real reader: `GraphStore.graph_version_at` answers
-- "which version had this org reached at instant T", which is the number an audit has to quote
-- because read models and reasoning runs are stamped with it, and `graph_versions` holds only the
-- current counter and cannot answer for the past.
--
-- It is NOT, despite its name and its column, an outbox anybody drains. `published_at` has never
-- been set by anything, so:
--
--   1. THE TABLE GREW WITHOUT BOUND. One row per event, for the life of the tenant, with no
--      retention anywhere in the engine. `analytic/history` carries the note about what that
--      shape costs — it is "the one store in L2 that only ever APPENDS, which is the exact shape
--      that put this database into read-only once before" — and that one has a 24-month horizon
--      enforced on a path that actually runs. This one had nothing.
--
--   2. ITS ONLY INDEX COVERED EVERY ROW AND SELECTED NOTHING. `change_outbox_unpublished` is
--      partial on `published_at is null`, which is true of 100% of the table and always has been.
--      A partial index whose predicate matches everything is not an index; it is a second copy of
--      the org_id column, maintained on every insert, serving no query.
--
--   3. THE READER'S OWN FILTER HAD NO INDEX. `graph_version_at` reads
--      `where org_id = :o and created_at <= :t`, and nothing indexed `created_at`.
--
-- RETENTION IS SAFE HERE BECAUSE THE READER ALREADY EXPECTS IT. `graph_version_at`'s docstring
-- says so in its own words: it returns None "when nothing was recorded before that instant (an org
-- with no committed change yet, or one whose outbox rows have aged out) — a null is honest here,
-- and a 0 would read as a real version". The horizon was anticipated; only the pruning was absent.
--
-- 24 MONTHS, matching `analytic/history.RETENTION_MONTHS`, so an audit can resolve a version for
-- exactly as long as this layer retains anything at all. A shorter horizon here would make a
-- metric point older than the outbox unresolvable to the version that produced it.

-- The index the reader and the prune both want. Not partial: every row is a candidate for both.
create index if not exists change_outbox_by_time
    on graph_change_outbox (org_id, created_at);

-- The index that matched everything. Dropped rather than kept "in case": it costs a write on
-- every committed event and answers no query in the engine. The column STAYS — a publisher may
-- yet exist, and the data it would need is the data that is there. Recreating this is one line:
--   create index change_outbox_unpublished on graph_change_outbox (org_id) where published_at is null;
drop index if exists change_outbox_unpublished;

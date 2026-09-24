-- 0179 · the four world instants a signal could not say.
--
-- THE DEFECT. `qualified_signals` carried three `_at` columns — `occurred_at`, `expires_at`,
-- `ingested_at` — and the last is a PROCESSING fact, not a world one. So **a signal could not say
-- "8 days overdue"**: the deadline lived inside `Commitment.due`, a claim nested in the extraction
-- jsonb, and nothing can sort, sweep or index a value that deep. Benchmark P2 asks exactly that
-- question of exactly this table.
--
-- `due_at` IS LIFTED, NEVER RE-DERIVED. `esqe/instants.due_at_of` reads it off the typed claim
-- ALG-09 already resolved, taking the FAR end of a range — a promise is overdue when the range the
-- speaker committed to has passed, and taking the near end invents a deadline. That is the failure
-- `Commitment`'s own contract names: *"an invented deadline must not be able to produce a false
-- overdue — it chases a founder about a deliverable that was never due."*
--
-- `superseded_at` IS NOT REDUNDANT WITH `supersedes`. That column is a POINTER, so *"when did this
-- stop being current"* was implied by another row's existence rather than stored — and a sweep
-- cannot filter on an implication. It is written by ALG-19 when the replacement arrives, not at
-- publish time, which is why the publisher deliberately leaves it null.
--
-- ALL FOUR NULLABLE. Most signals have no deadline and were never resolved; a NOT NULL would force
-- every writer to invent one, and an invented instant is worse than an absent one. Every row
-- written before this migration is correctly null.
--
-- TIMESTAMPTZ, matching the three that already exist. `contracts/signal.instants_are_ordered`
-- refuses a naive datetime at the boundary for the same reason the column is tz-aware here: a naive
-- instant compares WRONGLY against every other timestamp in the system rather than failing.
--
-- Idempotent: add-if-not-exists throughout, safe to re-run.
alter table qualified_signals
    add column if not exists due_at         timestamptz,
    add column if not exists effective_at   timestamptz,
    add column if not exists resolved_at    timestamptz,
    add column if not exists superseded_at  timestamptz;

-- "What is overdue for this tenant, soonest first" is the one question these columns exist to make
-- answerable, and it is the sweep P2 rests on. Partial on `due_at is not null`, because the rows
-- that matter are the minority that carry a deadline at all.
create index if not exists qualified_signals_due
    on qualified_signals (org_id, due_at)
 where due_at is not null;

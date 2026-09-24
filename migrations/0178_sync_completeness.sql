-- 0178 · `l1_sync_runs` learns whether a sweep FINISHED.
--
-- THE DEFECT. `api/routes.py` logs "backfill drain done" whether the provider ran out of mail or
-- the 500-page runaway guard stopped us halfway through a tenant's history, and `l1_sync_runs`
-- (0027) has fifteen columns of which not one can answer "was this complete?":
--
--     run_id · org_id · connection_id · source · mode
--     scanned · emitted · dropped · parked · duplicate · quarantined
--     error · started_at · finished_at
--
-- So a backfill that stopped at page 500 files `scanned=50000` and reads, forever, exactly like
-- one that reached the end of the mailbox. That is the benchmark's own headline failure committed
-- by our ingestion: Gemini reported "18 threads read of 18 that exist" against a mailbox of ~465
-- — the size of what it read as the size of what exists — and every negative answer built on a
-- truncated sweep ("you have no follow-up from Acme") inherits the same lie.
--
-- NOT A NEW TABLE. The step plan called for a `sync_completeness` table keyed on
-- (connection, window, run). `l1_sync_runs` is already one row per run carrying connection_id,
-- source and mode, written by the single `api/routes._run_ledger`. Columns here mean no second
-- writer and nothing that can drift from the first.
--
-- `cursor_exhausted` IS THREE-VALUED AND THAT IS THE POINT:
--
--     true    the provider said there is no more. Complete FOR THIS WINDOW — never for "all
--             history", because the window is a per-connection `backfill_days` setting (60 by
--             default, migration 0082).
--     false   there is more and we stopped. `page_budget_spent` says who.
--     null    NOT APPLICABLE, or not measured. A webhook has no pagination to exhaust, and every
--             row written before this migration has no answer. Storing `true` for either would be
--             the fabricated 100% the whole unit exists to prevent.
--
-- NULLABLE, DELIBERATELY. A `not null default false` would state that every sweep this product
-- has ever run was INCOMPLETE — a claim about the past that nobody measured, and one that would
-- put a false "your history is truncated" banner in front of every existing tenant.
--
-- `claimed_total` IS THE DENOMINATOR and `claimed_is_estimate` travels with it because Gmail's
-- `resultSizeEstimate` is exactly that. An estimate stored without its label becomes a fact at
-- the first reader. It also makes fetched > claimed legible rather than alarming: that is LEGAL
-- when the estimate runs low, and a checker that treated the excess as an error would raise on a
-- perfectly correct sweep.
--
-- Idempotent: add-if-not-exists throughout, safe to re-run.
alter table l1_sync_runs
    add column if not exists cursor_exhausted    boolean,
    add column if not exists page_budget_spent   boolean,
    add column if not exists claimed_total       integer,
    add column if not exists claimed_is_estimate boolean;

-- "Show me the incomplete sweeps for this tenant, newest first" is the one question this step
-- exists to make answerable, so it is an index scan rather than a scan of every run ever made.
-- Partial on `cursor_exhausted is false`, because the rows that matter are the rare ones.
create index if not exists l1_sync_runs_incomplete
    on l1_sync_runs (org_id, finished_at desc)
 where cursor_exhausted is false;

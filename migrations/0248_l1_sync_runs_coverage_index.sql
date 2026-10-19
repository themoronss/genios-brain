-- 0248 · l1_sync_runs — the two indexes the coverage reads ask for (L1 rebuild C1).
--
-- WHY. Two readers ask this ledger "which runs of THIS source / THIS mailbox finished in a window?"
-- (`capture/coverage/window.coverage_for_window`, `.coverage_for_connection`), and a third asks which
-- sources ran at all (`context/situations`). The only index was (org_id, finished_at desc) from 0027,
-- so each read walked every run the org ever wrote and filtered `source` / `connection_id` row by
-- row. Measured on production over 3.5 days (18 Oct, one org): 21,570 sequential scans of the table,
-- 34.4 million rows read, for a ledger of 1,692 rows; the window read alone ran 15,664 times.
--
-- WHAT. One index per question, each ending in finished_at so the window is a range on it:
--   (org_id, source, finished_at)         — the per-source window and the distinct-source read
--   (org_id, connection_id, finished_at)  — the per-mailbox window
--
-- ADDITIVE AND IDEMPOTENT: indexes only, `if not exists`; no column, no row and no reader changes, so
-- the previous image runs unchanged against it.

create index if not exists l1_sync_runs_by_org_source
    on l1_sync_runs (org_id, source, finished_at);
create index if not exists l1_sync_runs_by_org_connection
    on l1_sync_runs (org_id, connection_id, finished_at);

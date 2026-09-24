-- 0180 · the proof behind a negative claim, carried on the signal.
--
-- THE DEFECT, and it is epistemic rather than technical:
--
--     "No follow-up email found" means nothing until you know whether the search covered
--     100% of the mail or 8% of it.
--
-- `qualified_signals.coverage_ready` is a BOOLEAN about channel connectivity — *"could a source
-- have carried this?"* That is a real question and a narrower one than *"how much of what that
-- source holds did we actually read?"*, and only the second makes a negative claim defensible.
--
-- Gemini's worst benchmark failure was exactly this: it reported the size of its context as the
-- size of the mailbox — "18 threads read of 18 that exist" against ~465. Claude's strongest
-- behaviour was publishing a coverage table BEFORE any finding.
--
-- WHAT THE BLOCK HOLDS: the window the claim rests on, and PER SOURCE the count indexed, the
-- provider's own total, whether that total is an estimate, whether the cursor exhausted, and the
-- completeness in integer basis points.
--
-- PER SOURCE AND NEVER BLENDED. A tenant with complete calendar coverage and 8% email coverage has
-- TWO different licences to make a negative claim, and one blended number would grant the stronger
-- one to both. "No meeting was booked" and "no follow-up was sent" rest on different evidence.
--
-- NULLABLE, AND NULL MEANS UNKNOWN — never "complete". Every signal written before this migration
-- has no coverage block, and the honest reading of that is *"we do not know"*. A NOT NULL with a
-- default would have to invent a value, and the only value it could invent is the one thing this
-- step exists to prevent.
--
-- FROZEN AT CAPTURE. The block is a jsonb VALUE, not a pointer: no org id, no query, no run id. A
-- signal that said "8% of the window indexed" keeps saying 8% after a backfill takes the tenant to
-- 100% — the claim was made with 8% of the evidence and its strength has not changed. Storing a
-- live reference would make yesterday's finding silently restate itself tonight, and nobody would
-- be told.
--
-- Idempotent: add-if-not-exists, safe to re-run.
alter table qualified_signals
    add column if not exists coverage jsonb;

-- "Which of this tenant's signals rest on a window we barely read" is the question an operator
-- asks when a negative claim looks wrong. Partial, because the rows that matter are the ones that
-- HAVE a block: a null is already findable with `coverage is null`.
create index if not exists qualified_signals_coverage
    on qualified_signals (org_id)
 where coverage is not null;

# Output, edge cases and gaps

**Output:** a result containing run ID, applied/already-ran flags, produced/inserted/re-evaluated/
unchanged objects, published/held/rejected/preflight-rejected/input-rejection counts, final state
counts, expired memory count and policy revision. The completed row persists the same result.

`objects_reevaluated` counts eligible held Observed/Candidate decisions. `objects_unchanged` counts
duplicates already beyond Candidate that were deliberately not reopened. Every actual evaluation
has its separate final sink-level reason in `learning_object_evaluations`.

Failure behavior:

- any exception rolls back the entire claimed analytical transaction—no half-published run;
- a separate transaction records only the exception class, never source content, and keeps the
  week retryable;
- retention already committed and is not resurrected by the later rollback; and
- one tenant failure is logged by the heartbeat without stopping other tenants or future ticks.

**Remaining operations requirement:** enable either the in-process scheduler or a production worker,
monitor failed/retried runs, and rehearse multi-replica PostgreSQL contention plus migration `0047`
on production-like data. The code path is replica-safe; deployment proof is environmental.

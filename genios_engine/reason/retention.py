"""Retention for the reasoning audit trail — the table family that filled the disk.

WHY THIS EXISTS. `reasoning_*` held 442 MB across ~96,000 rows on 2026-09-16, accumulated in ONE
month, and nothing had ever deleted a row of it. The database reached 1,045 MB against a 500 MB
tier and Supabase flipped it read-only, which stops every write the product makes — not only this
one. `expertise_packages` has had a purge since the 995 MB incident; this family never got one.

The growth is not a leak. Every reasoning run legitimately writes a candidate set, a check per
candidate per evaluator, a reasoner result per unit and an output — a fully auditable decision, by
design. What was missing is the other half of an audit trail: the point at which it stops being
evidence and becomes cost. Measured on the same day: 4,758 runs, of which 130 were still
referenced by a signal. NINETY-SEVEN PERCENT of the trail belonged to runs nothing pointed at.

WHAT MAKES THIS SAFE, AND IT IS NOT THIS MODULE'S CARE. A card's right to exist is
`reason/authority.AUTHORITATIVE_SIGNAL_PREDICATE`, which joins a signal to five reasoning tables.
Deleting any row under a live card would not raise — the card would simply stop matching the
predicate and vanish, silently, which is the worst failure this codebase produces. The database
refuses it instead: `signals` holds `ON DELETE NO ACTION` foreign keys to `reasoning_runs`,
`reasoning_candidates` and `reasoning_run_outputs`, so Postgres will not let a referenced run go
however this module is called or mis-called. The `where not exists` below is what keeps the
statement from ERRORING; the constraint is what keeps it from being wrong.

WHY THE UNIT IS THE RUN. `reasoning_candidates`, `reasoning_reasoner_results` and
`reasoning_run_outputs` all carry `ON DELETE CASCADE` to `reasoning_runs`, and
`reasoning_candidate_checks` cascades from candidates. So one delete of an aged, unreferenced run
takes its whole subtree with it and no child can be orphaned by a partial pass.

WHY A GRACE PERIOD AT ALL, when the reference check already protects the trail: a run is written
BEFORE the signal that points at it. A purge racing a sweep would find a seconds-old run with no
signal yet and be entirely correct to delete it, and entirely wrong. Seven days is far longer than
that race and far shorter than the 28-day window `feedback/calibrate` reads — and calibration
reaches a run THROUGH its signal, so anything it can still see is referenced and already exempt.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

logger = get_logger(__name__)

#: How long an unreferenced run is kept before it is purged. See WHY A GRACE PERIOD in the module
#: docstring — this is a race window, not a retention promise, and the reference check is what
#: actually protects anything worth keeping.
KEEP_DAYS = 7

#: One aged, unreferenced run at a time, in batches, so a first pass over a year of backlog cannot
#: hold a lock long enough to matter to the sweep running beside it. A cascade of one run touches
#: roughly fourteen rows on this tenant, so a batch of 500 is about seven thousand deletes.
BATCH = 500

_PURGE_RUNS = text("""
    delete from reasoning_runs
    where (org_id, run_id) in (
        select rr.org_id, rr.run_id from reasoning_runs rr
        where rr.started_at < :cutoff
          and not exists (select 1 from signals s
                          where s.org_id = rr.org_id and s.reasoning_run_id = rr.run_id)
        limit :batch)
""")

#: A context snapshot outlives the runs that read it and is shared by several, so it cannot cascade
#: from one. `reasoning_context_payloads` and `reasoning_evidence_digests` both CASCADE from it,
#: which is where the last of the family goes.
#: NO TABLE ALIAS IN A `DELETE`. Postgres accepts one and SQLite does not, and the unit tests run
#: on SQLite — an aliased statement would be unreachable by every test that exists to check it,
#: which is how a Postgres-only `= any(:ids)` hid a defect in `_reconcile` for as long as it did.
_PURGE_CONTEXT = text("""
    delete from reasoning_context_snapshots
    where created_at < :cutoff
      and not exists (
        select 1 from reasoning_runs rr
        where rr.org_id = reasoning_context_snapshots.org_id
          and rr.context_snapshot_id = reasoning_context_snapshots.context_snapshot_id)
""")

#: Shared by many runs, referenced by context snapshots, and cascades from neither.
_PURGE_CAPABILITY = text("""
    delete from reasoning_capability_snapshots
    where created_at < :cutoff
      and not exists (
        select 1 from reasoning_runs rr
        where rr.org_id = reasoning_capability_snapshots.org_id
          and rr.capability_snapshot_id = reasoning_capability_snapshots.capability_snapshot_id)
      and not exists (
        select 1 from reasoning_context_snapshots cs
        where cs.org_id = reasoning_capability_snapshots.org_id
          and cs.capability_snapshot_id = reasoning_capability_snapshots.capability_snapshot_id)
""")


def purge_expired_reasoning(engine, *, keep_days: int = KEEP_DAYS,
                            now: datetime | None = None,
                            max_batches: int = 40) -> dict[str, int]:
    """Delete aged reasoning runs nothing references, and whatever is left holding nothing.

    Returns `{runs, context_snapshots, capability_snapshots}` — counts, so a heartbeat that
    reports zero is distinguishable from one that did not run. NEVER RAISES past the caller's own
    guard: the maintenance sweep must survive a retention pass that could not complete, because a
    tick that dies here stops billing, distribution and learning as well.

    THREE PASSES IN ORDER, and the order is the dependency order. Runs go first and take their
    candidates, checks, results and outputs with them by cascade. Context snapshots can only be
    judged once the runs that referenced them are gone. Capability snapshots last, because a
    context snapshot may still hold one.

    `max_batches` bounds a single tick rather than the total: a database with a year of backlog
    should be drained over several ticks, not in one statement that holds locks while the sweep it
    runs inside is trying to write.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(0, int(keep_days)))
    out = {"runs": 0, "context_snapshots": 0, "capability_snapshots": 0}
    with engine.begin() as conn:
        for _ in range(max(1, int(max_batches))):
            removed = conn.execute(_PURGE_RUNS, {"cutoff": cutoff, "batch": BATCH}).rowcount or 0
            out["runs"] += removed
            if removed < BATCH:
                break
        out["context_snapshots"] = conn.execute(
            _PURGE_CONTEXT, {"cutoff": cutoff}).rowcount or 0
        out["capability_snapshots"] = conn.execute(
            _PURGE_CAPABILITY, {"cutoff": cutoff}).rowcount or 0
    if any(out.values()):
        logger.info("reasoning retention: %s", out)
    return out


__all__ = ["BATCH", "KEEP_DAYS", "purge_expired_reasoning"]

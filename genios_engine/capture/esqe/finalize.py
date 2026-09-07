"""L1.6.10 · THE ONE FINALIZER — the four things Layer 1 does after a door has captured events.

`_run_ledger` in `api/routes.py` grew this sequence one line at a time, and every one of the four
comments in it makes the same argument: *this is the one hook every `run_sync` caller already
reaches, so "the floor ran" does not depend on which of the six sync call sites remembered to ask
for it.* The argument is right and it is exactly one door wide. The UPLOAD door does not call
`run_sync`; it calls `intake.ingest_manual` per chunk, so a file a founder deliberately handed us
— a signed contract, a price list, an audit checklist — captured, extracted and scored, and then
its signals fell on the floor of the function that captured them. Nothing errored. `qualified_
signals` simply had no row for the one source the tenant chose by hand.

That is the defect the build record names six times over — *a unit built, tested, and called by
nothing on a real request path* — reappearing as a unit called by ONE path and not the others. The
fix is not a second copy of the sequence in `upload_routes.py`; two copies drift, and the half
that drifts is invisible because both sides still typecheck. It is this module: the sequence
written once, taking its stores as an argument, so a new capture door is one call rather than
forty lines somebody has to remember to copy.

**The order is the design, and it is preserved exactly.**

    conflicts   filed FIRST and unconditionally — ALG-12 retained both sides of a disagreement so
                a human could look, and a record that is meant to be permanent must not be
                conditional on a subsystem it has no relationship with (defect D8).
    qualify     ALG-18's floor, per tenant, with every refusal filed to `qualification_drops`. A
                signal it could not SCORE travels; only a scored signal below the floor stops.
    lifecycle   ALG-19 ages what this tenant already holds — expiries and supersessions — BEFORE
                publication, so a stored row carries the state the lifecycle pass decided rather
                than a publisher's guess of `active`.
    publish     V-1..V-7 over what qualified, into `qualified_signals`. The L1 -> L2 boundary.

**Never raises, on the same terms as the four functions it calls.** Each of them is already
guarded internally and each returns an empty result on failure; this function adds no new failure
mode of its own, because everything it does is downstream of capture and capture is the part the
tenant paid for. Losing a published row costs a card. Raising costs the tenant their mail.

**No clock.** Every instant comes from the summary the door already froze (`sweep_eval_time`), so
a replay of yesterday's upload qualifies against yesterday.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from genios_engine.capture.esqe.lifecycle import LifecycleOutcome, outcome_digest, sweep_lifecycle
from genios_engine.capture.esqe.publisher import publish_sweep
from genios_engine.capture.esqe.qualification import QualificationOutcome, qualify_sweep
from genios_engine.capture.validate.conflict_store import persist_sweep_conflicts
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.finalize")


@dataclass(frozen=True)
class L1Stores:
    """The seven places Layer 1's conclusions are written, as ONE argument.

    Seven keyword arguments at every call site is seven chances to pass six; a bundle makes the
    omission a construction the reader can see. Every one is optional for the same reason the
    stores themselves are: a dev run with no database still captures, still scores, and simply
    keeps nothing — the in-memory implementations are the same shape.
    """

    conflicts: Any = None
    floors: Any = None
    drops: Any = None
    lifecycle: Any = None
    signals: Any = None
    parked: Any = None
    rejections: Any = None


@dataclass(frozen=True)
class ManualSweep:
    """A capture that was not a connector sweep, in the shape the four ESQE seams read.

    `qualify_sweep`, `sweep_lifecycle` and `publish_sweep` are all duck-typed on a summary — they
    read `org_id`, `results` and `conflicts` and nothing else — and that is deliberate: it is what
    lets a door that has `CaptureResult`s but no `SyncSummary` (an upload, a webhook replay, a
    manual re-run) reach the same seam without inventing a fake connector run around itself.

    `conflicts` is None because ALG-12's lane is scoped to one connector sweep: an upload's chunks
    are slices of ONE document and disagree with nothing until the graph compares them with what
    another source said, which is L2's question. `sweep_eval_time` then falls through to the
    latest `occurred_at` among the captured events — a stored world time, so this replays.
    """

    org_id: str
    results: tuple = ()
    conflicts: Any = None
    #: The counts a caller may want to log. Not read by any ESQE seam.
    emitted: int = 0
    scanned: int = 0
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FinalizeOutcome:
    """What the finalizer decided, for a caller that wants to log or assert on it."""

    qualification: QualificationOutcome
    lifecycle: LifecycleOutcome | None = None
    published: int = 0
    retired: int = 0


def finalize_l1(summary: Any, *, org_id: str, stores: L1Stores) -> FinalizeOutcome:
    """File the conflicts, run the floor, age the signals, publish what survived. In that order.

    `summary` is anything carrying `org_id`, `results` and (optionally) `conflicts` — a
    `SyncSummary` from `run_sync`, or a `ManualSweep` from a door that has neither.
    """
    persist_sweep_conflicts(summary, org_id=org_id, store=stores.conflicts)
    qualification = qualify_sweep(summary, org_id=org_id, floor_store=stores.floors,
                                  ledger=stores.drops)
    lifecycle = sweep_lifecycle(summary, org_id=org_id, store=stores.lifecycle)
    if lifecycle.transitions:
        # ALG-19's REPLAY CHECK on the path that produces the states: a stable fingerprint of what
        # this sweep decided, which is what an operator compares instead of eyeballing a list.
        _log.info("lifecycle swept org=%s transitions=%d records=%d digest=%s",
                  org_id, len(lifecycle.transitions), len(lifecycle.records),
                  outcome_digest(lifecycle))
    retired = 0
    # ALG-19's verdict carried onto the table LAYER 2 ACTUALLY READS. `sweep_lifecycle` writes to
    # `signal_lifecycle`; `context/situation_bso.gather_l1_signals` filters on
    # `qualified_signals.state`, and the signals ALG-19 retires are the ones an EARLIER sweep
    # published, which `publish_sweep` never revisits. Without this the two tables disagree
    # permanently and a founder is nudged about a renewal a later email already replaced.
    # `hasattr` because a dev store older than this method must not take the sweep down.
    if lifecycle.records and hasattr(stores.signals, "apply_lifecycle"):
        retired = stores.signals.apply_lifecycle(lifecycle.records)
        if retired:
            _log.info("lifecycle retired %d stored signal(s) org=%s", retired, org_id)
    report = publish_sweep(summary, qualification, org_id=org_id, store=stores.signals,
                           parked_store=stores.parked, rejections=stores.rejections,
                           lifecycle=lifecycle)
    # `stored`, not `len(emitted)`: the store logs and returns 0 on a database error rather than
    # raising, so a publish that DECIDED emit and wrote nothing must not report as a success.
    return FinalizeOutcome(qualification=qualification, lifecycle=lifecycle,
                           published=int(getattr(report, "stored", 0) or 0), retired=retired)


__all__ = ["FinalizeOutcome", "L1Stores", "ManualSweep", "finalize_l1"]

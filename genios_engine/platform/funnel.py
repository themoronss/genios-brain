"""The five-stage funnel — one writer per number, and a zero is a number.

    signals_detected -> situations_formed -> capability_resolved -> decision_emitted -> card_delivered

⛔ WHY THIS EXISTS. Grepped 2026-09-30: all five names had **zero hits** across `genios_engine/` and
`migrations/`. So the product could say how many cards it produced and nothing else — *"we made 28
cards"* and *"we made 28 out of 4,000 signals and lost 3,900 at a step nobody can name"* were the same
sentence.

Every layer in this programme found at least one defect a funnel count would have surfaced years
earlier: `l4_bundle` at 0 successes from 600 calls; a five-day total model outage, twice; 467 situations
held with nobody asking why; three modules built, tested, green and called by nothing. Each was found by
hand, by reading the graph against the cards.

⛔ WHY THIS LIVES IN `platform/` AND NOT IN A LAYER. Five different packages write these five numbers —
`capture` (layer 1) through `deliver` (layer 6). A writer in any one of them would be imported upward by
at least three others, and `tests/test_layer_topology.py` fails the build on an upward import. It caught
`capture/acquire/need_executor.py` doing exactly that earlier today. `platform/` is cross-cutting, so it
is the only home that does not make the dependency graph a lie.

⛔ ONE WRITER PER NUMBER, AND NEVER A CENTRAL COLLECTOR. A collector must re-derive four numbers it did
not compute, and a re-derived count can disagree with the thing it counts — at which point there are two
answers to "how many situations formed?" and no way to tell which is the measurement. This is the same
rule `contracts/reasoning.DECISION_PROJECTIONS` already applies to the decision: every projection names
its single writer.

⛔ AND A ZERO IS WRITTEN, NOT SKIPPED.

    situations_formed = 0   the stage RAN and formed nothing
    (no row)                nobody looked

Those are different facts, and this programme has already been caught twice by conflating a count with
its absence — `no_model_wired` in L1 and the graph-revision guard in L3. `record()` therefore writes
whatever it is given, including zero, and only a caller that genuinely did not run should not call it.

NEVER RAISES. A lost measurement costs a cycle of visibility; a raise costs the tenant their mail. Same
trade `detect_residue` and the evidence-need filing already make.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.funnel")

#: ⛔ The five stages, in flow order, and the vocabulary is CLOSED — migration 0188 has the same list
#: as a check constraint. An open vocabulary makes "is the funnel complete?" unanswerable, because a
#: typo becomes a sixth stage nobody notices.
SIGNALS_DETECTED = "signals_detected"
SITUATIONS_FORMED = "situations_formed"
CAPABILITY_RESOLVED = "capability_resolved"
DECISION_EMITTED = "decision_emitted"
CARD_DELIVERED = "card_delivered"

STAGES: tuple[str, ...] = (SIGNALS_DETECTED, SITUATIONS_FORMED, CAPABILITY_RESOLVED,
                           DECISION_EMITTED, CARD_DELIVERED)

#: ⛔ NOT A STAGE — the LOSS at `capability_resolved`, and the one gate the funnel could not explain.
#:
#: `reason/runner.run`'s per-node loop skipped a subject with no rule and no native capability on a
#: bare `continue`: no counter, no receipt, nothing. That is the Atlas's gate 3 — *"no authored
#: expertise, so an empty package"* — and it was the single largest unexplained drop in the product
#: while being literally uncounted.
#:
#: It is deliberately kept OUT of `STAGES`: migration 0188 carries the same five-name list as a check
#: constraint, and a sixth value would be a schema change for a number that is a reason rather than a
#: stage. It travels on the sweep's `outcomes` counter beside `muted`, `below_gate` and `cooldown`,
#: which is where every other "why did this subject say nothing" already lives.
NO_CAPABILITY = "no_capability"

#: ⛔ Which package owns each number. Stated as data so the "one writer per number" rule is checkable
#: by a test rather than asserted in a comment — `DECISION_PROJECTIONS` does the same thing for the
#: decision object. A second package writing someone else's stage is the failure this names.
STAGE_OWNERS: Mapping[str, str] = {
    SIGNALS_DETECTED: "capture",
    SITUATIONS_FORMED: "context",
    CAPABILITY_RESOLVED: "reason",
    DECISION_EMITTED: "reason",
    CARD_DELIVERED: "deliver",
}

_UPSERT = text(
    "insert into pipeline_counters (org_id, sweep_id, stage, n, sweep_at) "
    "values (:org_id, :sweep_id, :stage, :n, :sweep_at) "
    # A re-run of one sweep overwrites its own row rather than appending a second, disagreeing
    # observation of the same pass. The primary key is the sweep, not the clock, so this is an
    # overwrite by construction.
    "on conflict (org_id, sweep_id, stage) do update set "
    "  n = excluded.n, sweep_at = excluded.sweep_at, written_at = now()")

_READ_SWEEP = text(
    "select stage, n from pipeline_counters where org_id = :o and sweep_id = :s")

_READ_LATEST = text(
    "select sweep_id, sweep_at, stage, n from pipeline_counters "
    "where org_id = :o order by sweep_at desc, sweep_id, stage limit :n")


def record(conn, *, org_id: str, sweep_id: str, stage: str, n: int,
           sweep_at: datetime) -> None:
    """Write one stage's count for one sweep. **Zero is a valid count and is written.**

    Takes a connection rather than an engine so a caller already inside a transaction writes its
    count in the same transaction as the work it counted — a count committed separately from the thing
    it describes can survive a rollback of that thing.
    """
    if stage not in STAGES:
        # Refused by name rather than by the database's check constraint, so the caller gets the list
        # instead of an IntegrityError three frames down.
        raise ValueError(f"{stage!r} is not a funnel stage; the five are {list(STAGES)}")
    if n < 0:
        raise ValueError(f"{stage} cannot be {n}: a negative count is not a small count, it is a "
                         f"broken writer")
    conn.execute(_UPSERT, {"org_id": org_id, "sweep_id": sweep_id, "stage": stage,
                           "n": int(n), "sweep_at": sweep_at})


def observe(store, *, org_id: str, sweep_id: str, stage: str, n: int,
            sweep_at: datetime) -> bool:
    """`record` in its own transaction, swallowing failure. For a caller holding no transaction.

    Returns whether it was written, so a caller that cares can say "unmeasured" rather than "zero".
    ⛔ That distinction is the whole point of the module and it must survive its own failure path.
    """
    try:
        with store.engine.begin() as conn:
            record(conn, org_id=org_id, sweep_id=sweep_id, stage=stage, n=n, sweep_at=sweep_at)
        return True
    except Exception:      # noqa: BLE001 — a measurement must never break the thing it measures
        _log.exception("funnel stage %s not recorded for org=%s sweep=%s", stage, org_id, sweep_id)
        return False


def read_sweep(conn, org_id: str, sweep_id: str) -> dict[str, int | None]:
    """One sweep's funnel, with `None` for a stage that wrote no row.

    ⛔ `None`, never `0`. A stage that did not run and a stage that counted nothing are the two facts
    this table exists to separate, and a reader that returned `0` for both would undo it at the last
    hop — the `not_carried` shape, at the read instead of the write.
    """
    rows = {r["stage"]: int(r["n"])
            for r in conn.execute(_READ_SWEEP, {"o": org_id, "s": sweep_id}).mappings()}
    return {stage: rows.get(stage) for stage in STAGES}


def biggest_loss(funnel: Mapping[str, int | None]) -> tuple[str, str, int] | None:
    """Which adjacent pair lost the most, as `(from_stage, to_stage, lost)`.

    ⛔ A pair with an unmeasured end is SKIPPED, not treated as a loss of everything. An unwritten
    stage looks like a total collapse to arithmetic, and reporting it as one would send somebody
    debugging a stage that simply never reported.
    """
    worst: tuple[str, str, int] | None = None
    for earlier, later in zip(STAGES, STAGES[1:]):
        before, after = funnel.get(earlier), funnel.get(later)
        if before is None or after is None:
            continue
        lost = before - after
        if lost > 0 and (worst is None or lost > worst[2]):
            worst = (earlier, later, lost)
    return worst


def read_latest(conn, org_id: str, *, limit: int = 50) -> list[dict]:
    """Recent counter rows, newest sweep first. For an operator, not for a decision."""
    return [dict(r) for r in conn.execute(_READ_LATEST, {"o": org_id, "n": limit}).mappings()]


__all__ = ["CAPABILITY_RESOLVED", "CARD_DELIVERED", "DECISION_EMITTED", "SIGNALS_DETECTED",
           "SITUATIONS_FORMED", "STAGES", "STAGE_OWNERS", "biggest_loss", "observe", "read_latest",
           "read_sweep", "record"]

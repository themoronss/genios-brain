"""L2 · the TRIAGED WORK QUEUE — a read, and only a read.

WHY THIS IS ITS OWN MODULE, which is the whole reason the file exists. The join below belongs, by
every instinct, inside `residue.read_residue`: it is one dict lookup per row against the queue that
function already returns. Putting it there failed `scripts/derivation_dag_check.py`, and the
failure was correct:

    context_angle_verdicts -> context_residue -> context_angle_verdicts

`residue.py` WRITES `context_residue`; the angle store READS `context_residue` and writes
`context_angle_verdicts`. The moment `residue.py` also reads verdicts, the module graph carries a
cycle — and the check's own sentence is the reason it may not be waived: *"a fact derived from a
fact derived from itself converges to whatever it started at and looks stable."* The cycle happens
to be benign at runtime, because `detect_residue` writes without ever reading a verdict and only
the READER joins. But "benign because of which function you happened to call" is exactly the
property that stops being true the first time somebody adds a filter to the detector, and it would
stop being true silently. A module that reads both tables and writes NEITHER cannot acquire that
bug: it has no outgoing edge to close a cycle with.

So `residue.py` stays a writer that reads its evidence, the angle store stays a writer that reads
its gate, and the place they meet is here, where nothing is written at all.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text

from genios_engine.context.residue import RESIDUE_BALL_IN_COURT, read_residue

#: Which angle speaks for which residue kind. A kind absent from this map is never triaged, which
#: is not an oversight: `open_loop_unreported` is keyed by LOOP ID and `signal_unreached` by SIGNAL
#: TYPE, and neither is a `graph_nodes` id — so neither can carry the subject-scoped `sees` slice
#: `angles/store._seen` builds, and no angle may gate on them. Only the two node-keyed kinds are
#: even eligible, and only the founder's own case has an angle today.
TRIAGE_ANGLE_BY_KIND: dict[str, str] = {RESIDUE_BALL_IN_COURT: "reply_owed_triage"}

#: The key a verdict arrives under on a queue row. Absent when no angle has spoken.
TRIAGE_KEY = "triage"

#: `refused = false` IS IN THE QUERY, so `unknowable` never crosses this seam and no reader has to
#: know which word meant "I could not tell" for the version that answered. An angle whose refusals
#: dominate is visible in `AngleRun.refused`, which is where that number belongs.
_VERDICTS = ("select angle_id, subject_ref, verdict from context_angle_verdicts "
             "where org_id = :o and refused = false and angle_id in :angles")


def _verdicts(conn, org_id: str) -> dict[tuple[str, str], str]:
    """`{(residue_kind, subject_ref): verdict}`, or nothing at all.

    GUARDED, AND THE GUARD IS THE POINT. `context_angle_verdicts` arrived in migration 0165; a
    database that predates it, a fixture that builds only the tables its own subject needs, or a
    driver that cannot run the query must all return the queue EXACTLY as it reads today —
    unordered — rather than fail a read that was working yesterday. An angle may only ever ADD.
    """
    by_angle = {angle: kind for kind, angle in TRIAGE_ANGLE_BY_KIND.items()}
    if not by_angle:
        return {}
    try:
        rows = conn.execute(text(_VERDICTS).bindparams(bindparam("angles", expanding=True)),
                            {"o": org_id, "angles": sorted(by_angle)}).mappings().all()
    except Exception:      # noqa: BLE001 — an ordering must never cost the queue itself
        return {}
    return {(by_angle[str(r["angle_id"])], str(r["subject_ref"])): str(r["verdict"])
            for r in rows if str(r["angle_id"]) in by_angle}


def triaged_residue(conn, org_id: str, *, kind: str | None = None,
                    limit: int = 100) -> list[dict[str, Any]]:
    """The work queue, with a verdict beside any row an angle has spoken about.

    THE ORDER IS NOT TOUCHED — still `first_seen_at` ascending, still longest-unexplained first.
    Sorting by a model's word would let an opinion decide what a reader sees first, which is the
    ranking the agreed law forbids: *a model may propose a situation; it may never rank one, and
    never produces a number a card asserts.* The verdict rides beside each row so a reader may
    order by it; the engine does not choose for them. `confidence_bp` is deliberately not carried
    at all — it is a model's own estimate, and nothing downstream should be able to mistake it for
    a measurement this layer made.
    """
    rows = read_residue(conn, org_id, kind=kind, limit=limit)
    # Read ONCE for the page, and only when a triaged kind is actually present — a caller asking
    # for `signal_unreached` pays nothing for an angle that does not look at it.
    if not any(str(row["residue_kind"]) in TRIAGE_ANGLE_BY_KIND for row in rows):
        return rows
    verdicts = _verdicts(conn, org_id)
    for row in rows:
        word = verdicts.get((str(row["residue_kind"]), str(row["subject_ref"])))
        if word is not None:
            row[TRIAGE_KEY] = word
    return rows


#: The angle that classifies one unresolved blocker, and the fact its answer is carried in.
BLOCKER_ANGLE_ID = "blocker_absence"
BLOCKER_KIND_FIELD = "blocker.absence_kind"

_BLOCKER_VERDICTS = ("select subject_ref, verdict from context_angle_verdicts "
                     "where org_id = :o and angle_id = :a and refused = false")


def blocker_absence_verdicts(conn, org_id: str) -> dict[str, str]:
    """`{subject_ref: verdict}` for the blocker angle, keyed exactly as the evaluator wrote them.

    THE KEYS ARE FANNED REFS, not node ids — `"<node>#<digest>"` — and the reader joins by
    rebuilding them through `contract.fan_subject_ref`, the same function the evaluator used. Two
    independent spellings of "how we name an item" is the trap `condition_situations` records
    against its own field name, and it fails silently in both directions.

    GUARDED FOR THE REASON `_verdicts` ABOVE IS. `context_angle_verdicts` arrived in migration
    0165, and a card that exists today must not stop existing because an ordering is unavailable.
    """
    try:
        rows = conn.execute(text(_BLOCKER_VERDICTS),
                            {"o": org_id, "a": BLOCKER_ANGLE_ID}).mappings().all()
    except Exception:      # noqa: BLE001 — a classification must never cost the card
        return {}
    return {str(r["subject_ref"]): str(r["verdict"]) for r in rows}


__all__ = ["BLOCKER_ANGLE_ID", "BLOCKER_KIND_FIELD", "TRIAGE_ANGLE_BY_KIND", "TRIAGE_KEY",
           "blocker_absence_verdicts", "triaged_residue"]

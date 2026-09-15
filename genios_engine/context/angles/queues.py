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
    # NO try/except HERE, DELIBERATELY. A guard that swallows a database error without
    # owning the transaction is not a guard: Postgres aborts the whole transaction on a
    # failed statement, so returning an empty default leaves every LATER query on the same
    # connection failing with `InFailedSqlTransaction`. Measured on the live tenant — one
    # missing table here silently emptied eleven other gathers and killed all twelve
    # readings. The single guard is `outreach_situations._optional`, which wraps the call
    # in a SAVEPOINT and therefore can actually undo it.
    rows = conn.execute(text(_VERDICTS).bindparams(bindparam("angles", expanding=True)),
                        {"o": org_id, "angles": sorted(by_angle)}).mappings().all()
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
    # NO try/except HERE, DELIBERATELY. A guard that swallows a database error without
    # owning the transaction is not a guard: Postgres aborts the whole transaction on a
    # failed statement, so returning an empty default leaves every LATER query on the same
    # connection failing with `InFailedSqlTransaction`. Measured on the live tenant — one
    # missing table here silently emptied eleven other gathers and killed all twelve
    # readings. The single guard is `outreach_situations._optional`, which wraps the call
    # in a SAVEPOINT and therefore can actually undo it.
    rows = conn.execute(text(_BLOCKER_VERDICTS),
                        {"o": org_id, "a": BLOCKER_ANGLE_ID}).mappings().all()
    return {str(r["subject_ref"]): str(r["verdict"]) for r in rows}


#: The angle that adjudicates one near-miss, and the key its answer arrives under.
CAMPAIGN_ANGLE_ID = "same_situation_two_threads"
VERDICT_KEY = "verdict"

_CAMPAIGN_VERDICTS = ("select subject_ref, verdict from context_angle_verdicts "
                      "where org_id = :o and angle_id = :a and refused = false")


def adjudicated_candidates(conn, org_id: str) -> list[dict[str, Any]]:
    """The near-miss queue with M-3's answer beside each entry, newest window first.

    NOTHING IS MERGED HERE, and the shape says so: this returns the CANDIDATES, annotated. A
    `one_campaign` verdict does not mint a campaign — `find_campaigns` remains the only thing that
    does, and it still requires the exact sentence. Turning an adjudicated candidate into a card is
    a separate decision with a separate name (`is_this_worth_a_card`), and it belongs to whoever
    makes it rather than to the angle that offered the opinion.

    An entry with no verdict is one nothing has answered yet — no asker was supplied, the budget
    ran out, or the model refused. It is returned unannotated rather than hidden, because a queue
    that shows only what a model reached is a queue that cannot be reviewed.
    """
    from genios_engine.context.angles.contract import fan_subject_ref
    from genios_engine.context.campaign_candidates import read_candidates

    found = list(read_candidates(conn, org_id))
    if not found:
        return []
    # NO try/except HERE — see `_verdicts`. A guard that cannot roll back its own failed
    # statement leaves the shared transaction aborted and empties every later gather silently.
    rows = conn.execute(text(_CAMPAIGN_VERDICTS),
                        {"o": org_id, "a": CAMPAIGN_ANGLE_ID}).mappings().all()
    verdicts = {str(r["subject_ref"]): str(r["verdict"]) for r in rows}

    node_id = _tenant_of(conn, org_id)
    out: list[dict[str, Any]] = []
    for candidate in found:
        entry = dict(candidate)
        word = verdicts.get(fan_subject_ref(node_id, str(candidate.get("candidate_id") or "")))
        if word is not None:
            entry[VERDICT_KEY] = word
        out.append(entry)
    out.sort(key=lambda e: str(e.get("first_sent") or ""), reverse=True)
    return out


def _tenant_of(conn, org_id: str) -> str:
    """The node the candidate queue hangs off — the same one the evaluator fanned subjects from."""
    from genios_engine.context.periodic import tenant_node_id

    return str(tenant_node_id(conn, org_id) or "")


__all__ = ["BLOCKER_ANGLE_ID", "BLOCKER_KIND_FIELD", "CAMPAIGN_ANGLE_ID", "TRIAGE_ANGLE_BY_KIND",
           "TRIAGE_KEY", "VERDICT_KEY", "adjudicated_candidates", "blocker_absence_verdicts",
           "triaged_residue"]

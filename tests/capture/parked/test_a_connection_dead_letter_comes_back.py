"""A dead letter that failed on the CONNECTION was the one nobody automated.

`requeue_dead_letters` exists because `ocr_unavailable` means "we could not read it yet", and
the day an engine is wired somebody has to say so to the whole backlog at once. The heartbeat
does the saying — but only when an OCR engine exists. That is the right trigger for a row that
could not be READ and the wrong one for a row that could not be FETCHED.

MEASURED ON THE LIVE DATABASE, 17 Sep 2026: 110 rows across two orgs sat dead-lettered carrying
`no live connector`, both orgs holding a `connected`, unexpired gmail row the whole time. They
would never have moved on their own, because the only thing that requeues them is an OCR engine
arriving for an unrelated reason.

THE SELECTION IS ON THE ERROR, NOT THE CODE, and that is the whole safety of it. DOC-02 covers
both "no connector" and "the provider says this attachment is gone"; requeueing the second is
five more attempts spent re-learning a fact that has not changed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from genios_engine.capture.parked.refetch import (  # noqa: E402
    NO_LIVE_CONNECTOR,
    AttemptFailure,
    InMemoryRefetchQueue,
    ParkStatus,
    RefetchCandidate,
    RefetchSettlement,
)

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
STALE = NOW - timedelta(days=30)


def _queue(*rows) -> InMemoryRefetchQueue:
    """rows: (event_id, reason_code, last_error)."""
    q = InMemoryRefetchQueue()
    for event_id, reason, error in rows:
        q.candidates[event_id] = RefetchCandidate(
            event_id=event_id, org_id="org_1", reason_code=reason,
            status=ParkStatus.DEAD_LETTER.value, object_type="email_message", source="gmail",
            source_object_id=f"msg_{event_id}", parent_object_id=None,
            connection_id="con_gone", parked_at=STALE, attempts=5, next_attempt_at=None)
        q.last_attempt_at[event_id] = STALE
        q.settlements.append(RefetchSettlement(
            event_id=event_id, org_id="org_1", status=ParkStatus.DEAD_LETTER.value, attempts=5,
            last_attempt_at=STALE, next_attempt_at=None, last_error=error,
            failure=AttemptFailure.TRANSIENT.value))
    return q


def _pending(q) -> set[str]:
    return {e for e, c in q.candidates.items() if c.status == ParkStatus.PENDING.value}


CONNECTOR_MISS = f"{NO_LIVE_CONNECTOR} 'gmail'"
PROVIDER_GONE = "RuntimeError: gmail attachment fetch failed for 1a04::ANGjdJ"


# =============================================================================================
# the 110
# =============================================================================================
def test_a_row_that_had_no_connector_comes_back():
    q = _queue(("e1", "DOC-02", CONNECTOR_MISS))

    assert q.requeue_dead_letters(eval_time=NOW, not_attempted_since=NOW - timedelta(days=7),
                                  last_error_prefix=NO_LIVE_CONNECTOR) == 1
    assert _pending(q) == {"e1"}


def test_it_reaches_every_code_the_connection_could_have_broken():
    """DOC-02, DOC-05 and DOC-06 all appeared among the 110. The failure is the connection, so
    the code it happened to be parked under says nothing about whether it can recover."""
    q = _queue(("a", "DOC-02", CONNECTOR_MISS), ("b", "DOC-05", CONNECTOR_MISS),
               ("c", "DOC-06", CONNECTOR_MISS))

    assert q.requeue_dead_letters(eval_time=NOW, not_attempted_since=NOW - timedelta(days=7),
                                  last_error_prefix=NO_LIVE_CONNECTOR) == 3


# =============================================================================================
# what it must not put back
# =============================================================================================
def test_a_provider_saying_the_attachment_is_gone_stays_dead():
    """Five more attempts re-learning a fact that has not changed."""
    q = _queue(("gone", "DOC-02", PROVIDER_GONE))

    assert q.requeue_dead_letters(eval_time=NOW, not_attempted_since=NOW - timedelta(days=7),
                                  last_error_prefix=NO_LIVE_CONNECTOR) == 0
    assert _pending(q) == set()


def test_the_two_are_separated_in_one_pass():
    """The live backlog holds both under the same reason code."""
    q = _queue(("miss", "DOC-02", CONNECTOR_MISS), ("gone", "DOC-02", PROVIDER_GONE))

    q.requeue_dead_letters(eval_time=NOW, not_attempted_since=NOW - timedelta(days=7),
                           last_error_prefix=NO_LIVE_CONNECTOR)

    assert _pending(q) == {"miss"}


def test_a_row_attempted_inside_the_window_is_left_alone():
    """The window is what stops an ungated pass becoming a loop: at most one ladder per row per
    week, which is the same argument the capability requeue already makes."""
    q = _queue(("fresh", "DOC-02", CONNECTOR_MISS))
    q.last_attempt_at["fresh"] = NOW - timedelta(hours=1)

    assert q.requeue_dead_letters(eval_time=NOW, not_attempted_since=NOW - timedelta(days=7),
                                  last_error_prefix=NO_LIVE_CONNECTOR) == 0


def test_without_the_filter_the_requeue_is_unchanged():
    """The parameter is additive: every existing caller passes nothing and gets what it got."""
    q = _queue(("miss", "DOC-02", CONNECTOR_MISS), ("gone", "DOC-02", PROVIDER_GONE))

    assert q.requeue_dead_letters(eval_time=NOW,
                                  not_attempted_since=NOW - timedelta(days=7)) == 2


# =============================================================================================
# the call site
# =============================================================================================
def _reconnect_call():
    """The `reconnected = queue.requeue_dead_letters(...)` statement, and how deeply it is
    nested. Parsed rather than grepped: "is this behind an if" is a question about the tree."""
    import ast
    import inspect

    from genios_engine.api import routes

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(routes)))
              if isinstance(n, ast.FunctionDef) and n.name == "_drain_attachment_refetch")
    for stmt in fn.body:                      # TOP LEVEL of the function only
        if (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)
                and getattr(stmt.value.func, "attr", "") == "requeue_dead_letters"
                and any(getattr(t, "id", "") == "reconnected" for t in stmt.targets)):
            return stmt.value
    return None


def test_the_heartbeat_requeues_them_without_waiting_for_an_ocr_engine():
    """The defect was not a missing function, it was the gate in front of it: a connection dead
    letter only ever came back if an engine arrived for an unrelated reason. Asserted on the
    TREE, because "unconditional" means the statement is not nested inside an `if` at all."""
    call = _reconnect_call()

    assert call is not None, (
        "no unconditional `reconnected = queue.requeue_dead_letters(...)` at the top level of "
        "_drain_attachment_refetch — the connection requeue is gated again, or gone")


def test_the_heartbeat_selects_on_the_connector_error():
    """Ungated AND unfiltered would put every provider failure back on the ladder every week."""
    call = _reconnect_call()
    kwargs = {k.arg for k in call.keywords}

    assert "last_error_prefix" in kwargs, "the heartbeat requeues every dead letter, not the "\
                                         "ones a connection can fix"
    prefix = next(k.value for k in call.keywords if k.arg == "last_error_prefix")
    assert getattr(prefix, "id", "") == "NO_LIVE_CONNECTOR", (
        "the heartbeat filters on a literal instead of the writer's own constant")


def test_the_heartbeat_keeps_the_window_that_stops_it_looping():
    """Without it the pass is a loop: the rows come back, spend five attempts, dead-letter, and
    the next beat requeues them again."""
    call = _reconnect_call()

    assert "not_attempted_since" in {k.arg for k in call.keywords}, (
        "the connection requeue has no age window — every beat re-runs the whole ladder")


def test_the_writer_emits_the_spelling_the_reader_selects_on():
    """The constant is only worth anything if `_attempt` actually writes it. A writer that drifts
    to its own wording leaves a filter matching nothing and a backlog that never moves — silently,
    because both halves still look correct on their own."""
    import ast
    import inspect

    from genios_engine.capture.parked import refetch as R

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(R)))
              if isinstance(n, ast.FunctionDef) and n.name == "_attempt")
    emitted = [n for n in ast.walk(fn)
               if isinstance(n, ast.Name) and n.id == "NO_LIVE_CONNECTOR"]

    assert emitted, ("_attempt no longer writes NO_LIVE_CONNECTOR, so the heartbeat's filter "
                     "matches nothing and connection dead letters never come back")

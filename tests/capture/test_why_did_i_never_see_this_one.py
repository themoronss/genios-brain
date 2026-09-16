"""L1.6.8's promise, tested about ONE event: *"why did I never see X?"*

`qualification.py` justifies the whole drop ledger on being able to answer that question in one
query, and every layer did write its refusal down. Nothing joined them, so the answer lived in
five tables and `event_trace` — the one holding most of the refusals — had no reader at all.

The four shapes below are the four answers a support ticket can have, and before this module the
first three were indistinguishable from each other and from the fourth:

    never captured        -> `found: false`
    stopped in the trace  -> the stage, the action, the reason code
    held for review       -> the parked row, its status and its code
    travelled             -> `stopped_by: null`

The fifth test is the one that matters most and is the easiest to get wrong: an event whose
signals PARTLY qualified. The drop ledger is per-signal, the question is per-event, and reporting
a drop as the answer for an event the founder did see is the most misleading thing this surface
could say.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.capture.journey import (TRACE_ADVANCING, TRACE_STOPPING, event_journey,
                                           unclassified_actions)

ORG = "org_journey"
T0 = datetime(2026, 9, 11, 15, 0, tzinfo=timezone.utc)


def _at(minutes: int) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat()


@pytest.fixture()
def engine():
    """The five tables this walks, with only the columns it reads. Real SQL, no doubles: the
    module's whole job is joining tables, and a fake engine would be testing the fake."""
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("create table source_events (event_id text, org_id text, source text, "
                       "object_type text, source_object_id text, occurred_at text, "
                       "captured_at text, outcome text, route text, triage_lane text, "
                       "internal_kind text)"))
        c.execute(text("create table event_trace (id integer primary key, org_id text, "
                       "event_id text, stage text, action text, reason_code text, detail text, "
                       "at text)"))
        c.execute(text("create table parked_events (org_id text, event_id text, stage text, "
                       "reason_code text, status text, refetch_failure_kind text, "
                       "created_at text)"))
        c.execute(text("create table qualification_drops (org_id text, event_id text, "
                       "signal_id text, signal_type text, subject_key text, importance_bp int, "
                       "importance_version text, floor_bp int, evaluated_at text)"))
        c.execute(text("create table publication_rejections (org_id text, event_id text, "
                       "signal_id text, signal_type text, outcome text, reason text, "
                       "rules text, evaluated_at text)"))
        c.execute(text("create table qualified_signals (org_id text, event_id text, "
                       "signal_id text, created_at text)"))
    return eng


def _event(eng, event_id: str, *, outcome: str = "emitted") -> None:
    with eng.begin() as c:
        c.execute(text("insert into source_events (event_id, org_id, source, object_type, "
                       "occurred_at, outcome, route) values (:e,:o,'gmail','email_message',"
                       ":t,:oc,'needs_extraction')"),
                  {"e": event_id, "o": ORG, "t": _at(0), "oc": outcome})


def _steps(eng, event_id: str, rows: list[tuple[str, str, str | None, int]]) -> None:
    with eng.begin() as c:
        for stage, action, reason, minute in rows:
            c.execute(text("insert into event_trace (org_id, event_id, stage, action, "
                           "reason_code, detail, at) values (:o,:e,:s,:a,:r,'{}',:t)"),
                      {"o": ORG, "e": event_id, "s": stage, "a": action, "r": reason,
                       "t": _at(minute)})


# =============================================================================================
# the four answers a support ticket can have
# =============================================================================================
def test_an_event_this_org_never_captured_says_so(engine):
    """`found: false` rather than a 404. "We never got it" and "we got it and refused it" are
    different tickets with different fixes, and a 404 makes them the same shrug."""
    journey = event_journey(engine, org_id=ORG, event_id="evt_never")

    assert journey["found"] is False
    assert journey["steps"] == []
    assert journey["stopped_by"] is None


def test_an_event_the_gate_refused_names_the_stage_and_the_rule(engine):
    """The measured case: 103 of the pilot org's events stopped here, and `/qualification/drops`
    reported every one of them as simply absent."""
    _event(engine, "evt_bulk")
    _steps(engine, "evt_bulk", [("landing", "pass", None, 1), ("S2", "pass", None, 2),
                                ("emit", "emit", None, 3),
                                ("s4_esqe", "short_circuit", "bulk_headers", 4)])

    stopped = event_journey(engine, org_id=ORG, event_id="evt_bulk")["stopped_by"]

    assert stopped == {"kind": "trace", "at": _at(4), "stage": "s4_esqe",
                       "action": "short_circuit", "reason_code": "bulk_headers", "detail": {}}


def test_an_event_held_for_review_says_which_queue_it_is_in(engine):
    """A park is recoverable and a drop is not, so a surface that blurs them sends the operator
    to the wrong place."""
    _event(engine, "evt_parked", outcome="parked")
    _steps(engine, "evt_parked", [("landing", "pass", None, 1), ("S1", "park", "DOC-02", 2)])
    with engine.begin() as c:
        c.execute(text("insert into parked_events (org_id, event_id, stage, reason_code, "
                       "status, created_at) values (:o,'evt_parked','S1','DOC-02','pending',:t)"),
                  {"o": ORG, "t": _at(3)})

    stopped = event_journey(engine, org_id=ORG, event_id="evt_parked")["stopped_by"]

    assert stopped["kind"] == "parked_events"
    assert (stopped["action"], stopped["reason_code"]) == ("pending", "DOC-02")


def test_a_floor_drop_carries_the_two_numbers_that_explain_it(engine):
    """`qualification_drops` has no reason column because its reason IS the comparison. Reporting
    two nulls would make the one ledger that stores a complete explanation look like the one that
    stores none."""
    _event(engine, "evt_floor")
    _steps(engine, "evt_floor", [("landing", "pass", None, 1), ("emit", "emit", None, 2)])
    with engine.begin() as c:
        c.execute(text("insert into qualification_drops (org_id, event_id, signal_id, "
                       "signal_type, subject_key, importance_bp, importance_version, floor_bp, "
                       "evaluated_at) values (:o,'evt_floor','sig_1','commitment_due',"
                       "'thread:abc:commitment',1920,'alg17-v1',2500,:t)"),
                  {"o": ORG, "t": _at(3)})

    stopped = event_journey(engine, org_id=ORG, event_id="evt_floor")["stopped_by"]

    assert stopped["kind"] == "qualification_drops"
    assert stopped["detail"]["importance_bp"] == 1920
    assert stopped["detail"]["floor_bp"] == 2500
    assert stopped["detail"]["signal_type"] == "commitment_due"


# =============================================================================================
# the one that is easy to get wrong
# =============================================================================================
def test_an_event_that_partly_qualified_was_not_stopped(engine):
    """ONE EVENT, UP TO FIVE SIGNALS. The floor refuses signals one at a time, so an event can
    hold a drop row and a qualified row at once — and it was SEEN. Answering "why did I never see
    this?" with a drop, for mail the founder did read, is worse than answering nothing."""
    _event(engine, "evt_mixed")
    _steps(engine, "evt_mixed", [("landing", "pass", None, 1), ("emit", "emit", None, 2)])
    with engine.begin() as c:
        c.execute(text("insert into qualification_drops (org_id, event_id, signal_id, "
                       "signal_type, importance_bp, floor_bp, evaluated_at) values "
                       "(:o,'evt_mixed','sig_low','deadline_stated',1200,2500,:t)"),
                  {"o": ORG, "t": _at(3)})
        c.execute(text("insert into qualified_signals (org_id, event_id, signal_id, created_at) "
                       "values (:o,'evt_mixed','sig_high',:t)"), {"o": ORG, "t": _at(3)})

    journey = event_journey(engine, org_id=ORG, event_id="evt_mixed")

    assert journey["stopped_by"] is None, (
        "an event the founder DID see is being reported as refused, because a per-signal ledger "
        f"was read as a per-event verdict: {journey['stopped_by']}")
    assert len(journey["ledgers"]["qualification_drops"]) == 1, "the drop is still reported"


def test_a_park_still_stops_an_event_that_has_a_qualified_signal(engine):
    """The exemption above is scoped to the per-signal ledgers. `parked_events` is per EVENT, so
    it must keep stopping one — otherwise a single qualified signal would hide the whole queue."""
    _event(engine, "evt_both", outcome="parked")
    _steps(engine, "evt_both", [("landing", "pass", None, 1)])
    with engine.begin() as c:
        c.execute(text("insert into parked_events (org_id, event_id, stage, reason_code, status, "
                       "created_at) values (:o,'evt_both','S1','DOC-06','pending',:t)"),
                  {"o": ORG, "t": _at(2)})
        c.execute(text("insert into qualified_signals (org_id, event_id, signal_id, created_at) "
                       "values (:o,'evt_both','sig_x',:t)"), {"o": ORG, "t": _at(2)})

    assert event_journey(engine, org_id=ORG, event_id="evt_both")["stopped_by"]["kind"] \
        == "parked_events"


# =============================================================================================
# the declaration, and the two callers that would go quiet without it
# =============================================================================================
def test_the_loss_partition_is_measured_not_assumed(engine):
    """`TRACE_ADVANCING | TRACE_STOPPING` is a CLAIM about a column. Here is its measurement."""
    _steps(engine, "evt_v", [("landing", "pass", None, 1), ("S1", "drop", "N-02", 2),
                             ("S1", "park", "DOC-02", 3), ("emit", "emit", None, 4),
                             ("s4_esqe", "short_circuit", "bulk_headers", 5)])

    assert unclassified_actions(engine, org_id=ORG) == []
    assert TRACE_ADVANCING & TRACE_STOPPING == frozenset(), "an action cannot both advance and stop"


def test_a_new_action_is_reported_rather_than_guessed(engine):
    """The failure this prevents: a sixth verb appears, the partition silently calls it
    advancing, and an event that was actually lost reads as still in flight."""
    _event(engine, "evt_new")
    _steps(engine, "evt_new", [("landing", "pass", None, 1)])
    with engine.begin() as c:
        c.execute(text("insert into event_trace (org_id, event_id, stage, action, detail, at) "
                       "values (:o,'evt_new','S9','quarantine','{}',:t)"),
                  {"o": ORG, "t": _at(2)})

    assert unclassified_actions(engine, org_id=ORG) == ["quarantine"]
    journey = event_journey(engine, org_id=ORG, event_id="evt_new")
    assert journey["steps"][-1]["advancing"] is None, "an unknown verb must not be guessed"
    assert journey["unclassified_actions"] == ["S9:quarantine"]


def test_the_api_actually_calls_the_walk():
    """Twice on this branch a passing unit test guarded a function with no caller."""
    from genios_engine.api import routes

    tree = ast.parse(inspect.getsource(routes))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "event_journey_report"), None)

    assert fn is not None, "the /events/{event_id}/journey route is gone"
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", None) == "event_journey"
               for n in ast.walk(fn)), "the route no longer calls event_journey"


def test_the_funnel_report_counts_losses_from_the_declared_set():
    """`1c` listed ('drop','park','emit') by hand and omitted `short_circuit`, so 245 refusals on
    the pilot org were missing from the one table that says which tool loses what. It reads the
    shared set now, and a second hand-written list here would be the same bug again."""
    # CODE ONLY — `ast.unparse` drops comments, and the comment explaining the old list quotes
    # it verbatim. Matching prose instead of code is how a guard passes on the wrong evidence.
    source = open("scripts/pipeline_funnel_report.py", encoding="utf-8").read()
    code = ast.unparse(ast.parse(source))

    assert "TRACE_STOPPING" in code, "the funnel report stopped using the declared loss set"
    for spelling in ("'drop','park','emit'", "'drop', 'park', 'emit'"):
        assert spelling not in code, f"the hand-written action list is back: {spelling}"

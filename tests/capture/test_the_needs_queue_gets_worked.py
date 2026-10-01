"""U10 · the pass that works the queue — and the two refusals that stop it destroying it.

    pytest tests/capture/test_the_needs_queue_gets_worked.py -q

⛔ THE TESTS THAT MATTER ARE THE REFUSALS. `need_id` is deterministic and the insert is `on conflict do
nothing`, so **a closure is permanent.** A need closed "unavailable: not connected" is a question
DESTROYED — when the connector arrives, nothing re-asks it, because the row says it was answered.

So a naive first run against today's production, where no connector is wired, would close the entire
queue and erase every question Layer 2 asked. That is strictly worse than never running the pass.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.evidence_need import BACKFILL_WINDOW, FETCH_THREAD, REEXTRACT
from genios_engine.capture.acquire.need_executor import (DEFAULT_LIMIT, NeedSweepReport,
                                                         build_fetchers, run_needs)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _row(need_id="en_1", subject_ref="signal:SIG-1", **over):
    row = {"need_id": need_id, "org_id": "o", "trace_id": "t",
           "question": "Is there source material we have not fetched?",
           "why_it_matters": "The situation cannot publish without it.",
           "subject_ref": subject_ref, "acceptable_sources": [], "unacceptable_sources": [],
           "window_from": None, "window_to": None, "max_cost_usd": None,
           "expires_at": None, "state": "open", "unavailable_reason": None}
    row.update(over)
    return row


class _Queue:
    """Stands in for `context/evidence_need_store`, which this layer may not import."""

    def __init__(self, rows=(), close_returns=True):
        self.rows = list(rows)
        self.closed: list[tuple[str, str, str | None]] = []
        self._close_returns = close_returns

    def read_open(self, org_id, limit=DEFAULT_LIMIT):
        return self.rows[:limit]

    def close(self, need_id, *, state, reason=None):
        self.closed.append((need_id, state, reason))
        return self._close_returns


def _found(source):
    return lambda need: {"source": source}


# =================================================================================================
# 1 · ⛔ REFUSAL 1 — no fetcher wired means the pass does not run at all
# =================================================================================================
def test_with_no_fetchers_the_pass_refuses_and_closes_nothing():
    """⛔ THE ONE THAT MATTERS MOST. Closing the queue as "not connected" records our own missing
    plumbing as a permanent fact about the tenant's evidence."""
    q = _Queue([_row(), _row("en_2")])
    report = run_needs("o", read_open=q.read_open, close=q.close, fetchers={}, eval_time=_NOW)

    assert report.ran is False
    assert report.refused and "no fetcher is wired" in report.refused
    assert q.closed == [], "a refused pass must not close a single need"
    assert report.examined == 0


def test_the_refusal_says_why_in_words_a_person_can_act_on():
    report = run_needs("o", read_open=_Queue().read_open, close=_Queue().close,
                       fetchers={}, eval_time=_NOW)
    assert "permanently erase" in report.refused


def test_build_fetchers_is_honestly_empty_today():
    """⛔ Returning `{}` is what makes the pass refuse, and that is correct rather than a placeholder.
    A stub returning `None` per fetch would close every need as "found nothing in the window" —
    indistinguishable from a real negative result, permanent, and wrong."""
    assert build_fetchers("o") == {}


def test_the_two_halves_compose_into_a_refusal_not_a_purge():
    """The composition root will wire exactly these two calls together. Today that must be a no-op,
    not a queue-clearing event."""
    q = _Queue([_row(), _row("en_2"), _row("en_3")])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers=build_fetchers("o"), eval_time=_NOW)
    assert report.ran is False
    assert q.closed == []


# =================================================================================================
# 2 · ⛔ REFUSAL 2 — a kind with no fetcher is DEFERRED, never closed
# =================================================================================================
def test_a_need_whose_kind_is_not_wired_is_left_open():
    """⛔ `fetch_thread` wired while `reextract` is not is the NORMAL state during a rollout, and those
    questions must survive it."""
    q = _Queue([_row(subject_ref="document:DOC-1")])          # wants REEXTRACT
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("gmail")}, eval_time=_NOW)

    assert report.ran is True
    assert report.deferred == 1
    assert report.closed == 0
    assert q.closed == [], "a deferred need must stay open"


def test_a_wired_kind_is_worked_while_an_unwired_one_waits_in_the_same_pass():
    q = _Queue([_row("en_thread", subject_ref="thread:T1"),
                _row("en_doc", subject_ref="document:D1")])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("gmail")}, eval_time=_NOW)

    assert report.met == 1
    assert report.deferred == 1
    assert [c[0] for c in q.closed] == ["en_thread"]


def test_deferred_is_not_counted_as_unavailable():
    """They are different facts: one is about our deployment, the other about the evidence."""
    q = _Queue([_row(subject_ref="document:D1")])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={BACKFILL_WINDOW: _found("gmail")}, eval_time=_NOW)
    assert report.deferred == 1
    assert report.unavailable == 0


# =================================================================================================
# 3 · what IS closed, and why that is right
# =================================================================================================
def test_a_need_no_layer_one_fetch_can_ever_answer_is_closed():
    """⛔ The distinction against REFUSAL 2: `plan_fetch` returning `None` is a fact about the
    QUESTION, not about our deployment. No connector will ever make it answerable."""
    q = _Queue([_row(subject_ref="capability:expertise.accounts")])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("gmail")}, eval_time=_NOW)

    assert report.unavailable == 1
    assert report.deferred == 0
    assert q.closed[0][1] == "unavailable"
    assert "no Layer 1 fetch answers" in q.closed[0][2]


def test_the_right_source_meets_the_need_and_the_closure_is_recorded():
    q = _Queue([_row(subject_ref="thread:T1")])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("signed_contract")}, eval_time=_NOW)
    assert report.met == 1
    assert q.closed == [("en_1", "met", None)]


def test_an_expired_need_closes_unavailable_rather_than_being_fetched():
    q = _Queue([_row(subject_ref="thread:T1", expires_at=_NOW - timedelta(hours=1))])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    assert report.unavailable == 1
    assert "expired" in q.closed[0][2]


def test_every_closure_carries_a_reason_when_it_is_unavailable():
    """The store refuses a reasonless closure, and so does the database. The pass must not be the
    thing that trips either."""
    q = _Queue([_row("en_a", subject_ref="capability:x"),
                _row("en_b", subject_ref="thread:T1", expires_at=_NOW - timedelta(days=1))])
    run_needs("o", read_open=q.read_open, close=q.close,
              fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    for _need_id, state, reason in q.closed:
        if state == "unavailable":
            assert reason and reason.strip()


# =================================================================================================
# 4 · ⛔ another pass got there first
# =================================================================================================
def test_losing_the_race_is_counted_not_retried():
    """⛔ Not an error. Another pass settled the question first and ITS answer stands; overwriting
    would reset `closed_at` and lose when it was actually settled."""
    q = _Queue([_row(subject_ref="thread:T1")], close_returns=False)
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)

    assert report.already_closed == 1
    assert report.met == 0
    assert len(q.closed) == 1, "a lost race is never retried"


# =================================================================================================
# 5 · the pass is bounded
# =================================================================================================
def test_the_queue_read_is_capped():
    q = _Queue([_row(f"en_{i}", subject_ref="thread:T1") for i in range(10)])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW, limit=3)
    assert report.examined == 3


def test_the_sweep_budget_defers_rather_than_closes():
    """⛔ A budget we ran out of is a fact about this pass, not about the evidence — so the rest stay
    open and the next pass reads the same queue, oldest first."""
    rows = [_row(f"en_{i}", subject_ref="thread:T1", max_cost_usd=0.60) for i in range(3)]
    q = _Queue(rows)
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW,
                       sweep_budget_usd=1.00)
    assert report.closed == 2
    assert report.deferred == 1


def test_an_empty_queue_is_a_clean_run_not_a_refusal():
    report = run_needs("o", read_open=_Queue().read_open, close=_Queue().close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    assert report.ran is True
    assert report.examined == 0 and report.closed == 0


# =================================================================================================
# 6 · ⛔ it never raises
# =================================================================================================
def test_a_broken_queue_read_does_not_break_ingestion():
    def boom(org_id, limit=DEFAULT_LIMIT):
        raise RuntimeError("database is down")

    report = run_needs("o", read_open=boom, close=_Queue().close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    assert report.ran is False
    assert "RuntimeError" in report.refused


def test_a_malformed_row_is_skipped_and_counted_not_fatal():
    """⛔ THE PERMANENT STALL, PREVENTED. The queue is read oldest-first, so a row that failed the whole
    pass would sit at its head forever and block every need behind it — invisibly. It is skipped,
    counted, and the rest are worked."""
    q = _Queue([{"need_id": "en_bad", "org_id": "o"},
                _row("en_good", subject_ref="thread:T1")])
    report = run_needs("o", read_open=q.read_open, close=q.close,
                       fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)

    assert report.ran is True
    assert report.malformed == 1
    assert report.met == 1, "the good need behind the bad row must still be worked"
    assert [c[0] for c in q.closed] == ["en_good"]


def test_a_malformed_row_is_never_closed():
    """We do not know what it was asking, so we cannot honestly record that it was answered."""
    q = _Queue([{"need_id": "en_bad", "org_id": "o"}])
    run_needs("o", read_open=q.read_open, close=q.close,
              fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    assert q.closed == []


def test_eval_time_is_carried_and_not_re_read():
    """Two runs at one instant must reach the same verdict on expiry."""
    rows = [_row(subject_ref="thread:T1", expires_at=_NOW + timedelta(hours=1))]
    a = run_needs("o", read_open=_Queue(rows).read_open, close=_Queue(rows).close,
                  fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    b = run_needs("o", read_open=_Queue(rows).read_open, close=_Queue(rows).close,
                  fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    assert (a.met, a.unavailable) == (b.met, b.unavailable)


# =================================================================================================
# 7 · ⛔ the layer boundary holds
# =================================================================================================
def test_this_module_does_not_import_context():
    """⛔ `capture/` is layer 1 and `evidence_needs` belongs to `context/` at layer 2. Importing the
    store here is an upward import, and `tests/test_layer_topology.py` fails the build on it — it
    caught this module's first draft. The queue arrives as callables instead."""
    import inspect

    from genios_engine.capture.acquire import need_executor

    assert "genios_engine.context" not in inspect.getsource(need_executor)


def test_the_report_distinguishes_all_five_things_that_can_happen():
    assert {f for f in NeedSweepReport.__dataclass_fields__} >= {
        "examined", "met", "unavailable", "deferred", "already_closed", "malformed", "refused"}

"""What the sweep must hand DOWN to each capture — Wave W9.

`run_sync` is the largest capture entry in the system and for its whole life it passed neither a
coverage declaration nor a semantic lane, so both seams were dead for the path that produces
almost every event. This file is about the FORWARDING, not about the units: the units have their
own tests, and what was broken was the wiring between them.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.parked.store import InMemoryParkedStore
from genios_engine.capture.semantic.model_router import T3Budget

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
OWNER = "founder@genios.ai"
MINIMAL_ANSWER = {"intent": "inform", "stance": "neutral"}

#: An email the tier router scores into T3: long content (+30), a currency token (+25), two date
#: strings (+20) and a deep thread (+15) = 90, against a T3 threshold of 75. Built from the score
#: table rather than tuned by trial, so a threshold change fails this loudly instead of quietly
#: turning the budget test back into a test of nothing.
_HEAVY_BODY = ("We can move forward with the $84,000 annual contract. Legal signs by "
               "October 15 and finance releases the first invoice on November 3. ") + ("x " * 2100)


class _Mailbox:
    """A connector with a stated set of messages and no network anywhere near it."""

    source = "gmail"

    def __init__(self, count: int = 3, *, body: str | None = None, extra: dict | None = None):
        self._objects = [
            RawObject(source="gmail", object_type="email_message",
                      source_object_id=f"msg_{i}", occurred_at=NOW,
                      actor_email="buyer@acme.com", recipients=(OWNER,),
                      raw={"subject": f"Contract {i}",
                           "body": f"Message {i}. " + (body or
                                   "We can move forward with the annual contract."),
                           **(extra or {})})
            for i in range(count)]

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def fetch_content(self, object_ref: str) -> dict:
        return {}


def _sweep(connector: _Mailbox | None = None, **kw):
    return run_sync(connector or _Mailbox(), org_id="org_sweep", connection_id="con_sweep",
                    repo=InMemorySourceEventRepository(), mailbox_owner=OWNER, **kw)


def test_a_sweep_without_either_seam_behaves_exactly_as_before():
    summary = _sweep()
    assert summary.emitted == 3
    assert all(g.coverage_ready is None for g in summary.gated)
    assert all(r.extraction is None for r in summary.results)


def test_the_declaration_reaches_every_event_of_every_page():
    """One `coverage_fn` for the sweep, consulted per event — not one verdict for the first
    message and None for the rest."""
    summary = _sweep(coverage_fn=lambda domain: {"coverage_ready": True})
    assert summary.emitted == 3
    assert [g.coverage_ready for g in summary.gated] == [True, True, True]


def test_the_lane_reaches_every_event_of_the_sweep(fake_llm):
    llm = fake_llm(*[MINIMAL_ANSWER] * 3)
    summary = _sweep(semantic=P.SemanticLane(llm=llm, eval_time=NOW))

    assert summary.emitted == 3
    assert llm.call_count == 3
    assert [r.extraction is not None for r in summary.results] == [True, True, True]


def test_a_failed_extraction_parks_without_failing_the_sweep(monkeypatch, fake_llm):
    """Park-never-drop, end to end. The message still emits; the park row lands in the sweep's own
    parked store, which is the queue a drain already reads — and the REST of the page is
    unaffected, which is the half a per-event try/except would get wrong.

    Pinned to one capture worker: `FakeLLM` hands out its canned answers in call order, and with a
    thread pool the two bad ones would be dealt to whichever messages raced first. That would make
    the park COUNT vary run to run — a flaky test dressed up as a concurrency test.
    """
    monkeypatch.setattr("genios_engine.capture.acquire.sync_runner._CAPTURE_WORKERS", 1)
    llm = fake_llm("not json", "still not json", MINIMAL_ANSWER, MINIMAL_ANSWER)
    parked = InMemoryParkedStore()
    summary = _sweep(semantic=P.SemanticLane(llm=llm, eval_time=NOW), parked_store=parked)

    assert summary.emitted == 3, "a model failure must not cost the tenant their mail"
    assert llm.call_count == 4, "one repair retry for the bad message, one call for each of the rest"
    assert [r.reason_code for r in parked.list("org_sweep")] == ["extraction_parse_failed"]
    assert [r.extraction is not None for r in summary.results] == [False, True, True]


def test_the_fixture_that_the_budget_test_depends_on_really_scores_t3(fake_llm):
    """Guard for the guard. If `_HEAVY_BODY` stopped reaching T3 the concurrency test below would
    pass while asserting nothing, which is the worst state a budget test can be in."""
    llm = fake_llm(MINIMAL_ANSWER)
    allowance = P.T3Allowance(T3Budget(t3_limit=10))
    _sweep(_Mailbox(1, body=_HEAVY_BODY, extra={"thread_depth": 4}),
           semantic=P.SemanticLane(llm=llm, eval_time=NOW, budget=allowance))
    assert allowance.budget.t3_granted == 1, (
        "_HEAVY_BODY no longer scores into T3, so the concurrency test below asserts nothing")
    assert allowance.budget.exhausted is False


@pytest.mark.parametrize("workers", [1, 4])
def test_concurrent_capture_never_double_spends_the_t3_allowance(monkeypatch, workers, fake_llm):
    """`sync_runner` captures a page on a thread pool. `route()` is pure — read a budget, return
    the next one — so N workers each reading the same immutable value would each be told they may
    spend it, and the daily allowance would be exceeded by exactly the worker count.
    `T3Allowance` serialises the read-decide-write; this asserts the COUNT, not the lock.
    """
    monkeypatch.setattr("genios_engine.capture.acquire.sync_runner._CAPTURE_WORKERS", workers)
    allowance = P.T3Allowance(T3Budget(t3_limit=1))
    llm = fake_llm(*[MINIMAL_ANSWER] * 12)
    summary = _sweep(_Mailbox(12, body=_HEAVY_BODY, extra={"thread_depth": 4}),
                     semantic=P.SemanticLane(llm=llm, eval_time=NOW, budget=allowance))

    assert summary.emitted == 12
    spent = allowance.budget
    assert spent.t3_granted == 1, (
        f"{spent.t3_granted} T3 extractions were granted against a limit of 1 — the allowance is "
        "being read by more than one worker before any of them writes it back")
    assert spent.t3_demoted == 11, "every extraction past the allowance must be a COUNTED demotion"

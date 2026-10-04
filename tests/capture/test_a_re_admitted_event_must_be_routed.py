"""An event put back into the pipeline is routed, or it is not back in the pipeline.

    pytest tests/capture/test_a_re_admitted_event_must_be_routed.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04, over 522 captured
gmail messages:

    emitted, route='needs_extraction'   57   extraction ran on all 57,   27 produced observations
    emitted, route IS NULL              77   extraction ran on NONE of them

    by day:   03 Oct  47 extracted / 29 not        04 Oct  10 extracted / 48 not

It was getting WORSE, because every drain re-admitted more parked rows into the same dead end.
Those 77 emails are in the database, counted as emitted, carrying their payload, and contributing
nothing — 495 of 522 messages produced no observation at all, and this is the largest single
reason.

⛔ THE CAUSE. `capture/pipeline` computes `triage_lane` and `route` ONLY when `gate.action` is
neither `drop` nor `park`, so a PARKED row is written with both NULL — correct, it has not been
admitted yet. The re-admission paths then flipped `outcome` to `'emitted'` and touched neither
column. `route` is exactly what the extraction lane selects on, so the row came back as emitted
and routed nowhere. There is ONE writer of `source_events` and its insert is `on conflict do
nothing`, so nothing downstream ever repaired it.

⛔ P3, NOT A GUESS AT URGENCY. `triage.triage_lane` scores urgency from the prepared content and
the re-admission paths do not hold it. P3 is that module's own "low-signal / digest / backfill",
which is what a row that sat in a park queue is. Understating is the safe direction: the event is
extracted, it just does not jump ahead of live mail. Overstating would let a recovered digest
preempt a customer's message.

⛔ `coalesce`, NOT AN OVERWRITE — `test_a_row_that_already_has_a_lane_keeps_it`. A row that
somehow carries a lane was triaged by the module that can actually score it, and this fallback
must never replace a real answer with its own.
"""

from __future__ import annotations

import inspect
import re

import pytest

from genios_engine.capture.parked import drain, recapture
from genios_engine.capture.triage.triage import triage_lane

pytestmark = pytest.mark.unit

#: Every place that turns a non-emitted row into an emitted one, and must therefore route it.
_READMITTERS = ((drain, "drain"), (recapture, "recapture"))


def _emitting_updates(module) -> list[str]:
    """Each `update source_events … set … outcome = 'emitted'` statement in the module."""
    source = inspect.getsource(module)
    return [m.group(0) for m in
            re.finditer(r"update source_events[^\"]*(?:\"\s*\"[^\"]*)*", source)
            if "emitted" in m.group(0)]


@pytest.mark.parametrize("module,name", _READMITTERS)
def test_a_re_admission_sets_a_route(module, name):
    """⛔ THE MUTATION THIS FILE REJECTS: flipping `outcome` without `route`. Seventy-seven live
    emails go back to being invisible work, and nothing anywhere reports it."""
    statements = _emitting_updates(module)
    assert statements, f"no emitting update found in {name} — re-point this test at it"
    for statement in statements:
        assert "route" in statement, (
            f"{name} re-admits an event without setting `route`; extraction selects on that "
            "column, so the row reads as emitted and reaches no lane")


@pytest.mark.parametrize("module,name", _READMITTERS)
def test_a_re_admission_sets_a_lane(module, name):
    for statement in _emitting_updates(module):
        assert "triage_lane" in statement, (
            f"{name} re-admits an event with no triage lane; nothing downstream can order it")


@pytest.mark.parametrize("module,name", _READMITTERS)
def test_a_row_that_already_has_a_lane_keeps_it(module, name):
    """⛔ `coalesce`, never a bare assignment. A row that carries a lane was scored by the module
    that can actually read the content; this fallback must not overwrite a real answer."""
    for statement in _emitting_updates(module):
        assert "coalesce(route" in statement and "coalesce(triage_lane" in statement, (
            f"{name} overwrites route/lane instead of filling them in — a real triage verdict "
            "would be replaced by the fallback")


def test_the_fallback_lane_is_one_triage_actually_produces():
    """P3 has to be a lane the rest of the system knows, not a new string invented here."""
    class _Ctx:
        sender_known = False
        is_structured = False
        raw = {"snippet": ""}

    assert triage_lane(_Ctx(), None) == "P3", (
        "P3 is no longer what triage returns for unremarkable content; the re-admission fallback "
        "now disagrees with the module it is imitating")


def test_the_fallback_is_the_lowest_lane_not_the_highest():
    """Understating is the safe direction. A recovered digest must never preempt live mail."""
    class _Urgent:
        sender_known = True
        is_structured = False
        raw = {"snippet": "URGENT: deadline tomorrow, can you confirm?"}

    assert triage_lane(_Urgent(), None) in ("P0", "P1")
    for module, _ in _READMITTERS:
        for statement in _emitting_updates(module):
            assert "'P3'" in statement, "the re-admission fallback claims a priority it cannot know"

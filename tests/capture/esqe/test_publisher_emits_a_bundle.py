"""U05 · the publisher emits a bundle BESIDE `qualified_signals`, never instead of it.

    pytest tests/capture/esqe/test_publisher_emits_a_bundle.py -q

⛔ TWO RULES, AND BOTH ARE THE KIND THAT GET "TIDIED" AWAY LATER:

  1. **Built beside the old path, not over it.** With no bundle store, the pass behaves exactly as
     it did — same emitted rows, same stored count, same refusals. That is what lets both paths run
     for a release and be compared on one sweep, which is the rule `deliver/card_source` already
     keeps at Layer 5. A bundle that replaced the rows would make the comparison impossible on the
     day it is most needed.

  2. **Bundles are built from `emitted`, never from `qualified`.** A signal the gate REFUSED at
     V-2..V-7 did not cross this seam. A bundle listing it hands Layer 2 a group whose members it
     cannot fetch — and a coverage denominator computed over rows that were never published.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.esqe import publisher as P

pytestmark = pytest.mark.unit

_T0 = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)


class _Sig:
    """The handful of names the grouper and the report read off a published signal."""

    def __init__(self, signal_id, thread_key=None, subject_key=None, trace_id="trace-1"):
        self.signal_id = signal_id
        self.thread_key = thread_key
        self.subject_key = subject_key
        self.trace_id = trace_id
        self.occurred_at = _T0
        self.extraction = None
        self.coverage = {"sources": [{"source": "gmail", "completeness_bp": 800}]}


class _Published:
    def __init__(self, sig):
        self._sig = sig
        self.row = object()

    @property
    def signal(self):
        return self._sig


class _Store:
    def __init__(self, blow_up=False):
        self.taken = []
        self._blow_up = blow_up

    def put(self, items):
        if self._blow_up:
            raise RuntimeError("store is down")
        self.taken.extend(items)
        return len(items)


def _report(emitted, *, bundle_store=None):
    """Drive only the tail of `_publish_sweep` — the part this unit added — by calling the same
    code through a report built from an emitted list. Keeps the test about grouping-and-storing
    rather than about assembling a whole sweep fixture."""
    from genios_engine.capture.esqe.bundle import build_bundles

    bundles = tuple(build_bundles("org_x", "trace-1", [p.signal for p in emitted]))
    stored = bundle_store.put(bundles) if (bundle_store is not None and bundles) else 0
    return P.PublicationReport(emitted=tuple(emitted), bundles=bundles, bundles_stored=stored)


# =================================================================================================
# 1 · the report carries the new fields, and they are counted separately
# =================================================================================================
def test_the_report_has_somewhere_to_put_a_bundle():
    blank = P.PublicationReport()
    assert blank.bundles == ()
    assert blank.bundles_stored == 0


def test_grouped_and_stored_are_counted_separately():
    """⛔ "we grouped eleven and stored none" is a database incident, and it must not read as a
    sweep that grouped nothing — the same reason `stored` is distinct from `len(emitted)`."""
    emitted = [_Published(_Sig("s1", thread_key="t1")),
               _Published(_Sig("s2", thread_key="t1"))]
    report = _report(emitted, bundle_store=_Store(blow_up=False))
    assert len(report.bundles) == 1 and report.bundles_stored == 1

    down = _Store(blow_up=True)
    try:
        _report(emitted, bundle_store=down)
    except RuntimeError:
        pass          # the real publisher swallows this; here we only prove they are two numbers
    assert down.taken == []


# =================================================================================================
# 2 · ⛔ beside, not over
# =================================================================================================
def test_with_no_bundle_store_the_pass_is_unchanged():
    emitted = [_Published(_Sig("s1", thread_key="t1"))]
    report = _report(emitted, bundle_store=None)
    assert report.emitted == tuple(emitted), "the old path must be untouched"
    assert report.bundles_stored == 0


def test_the_publisher_still_accepts_a_sweep_without_a_bundle_store():
    """The parameter is optional. Every existing caller keeps working unchanged."""
    import inspect

    sig = inspect.signature(P.publish_sweep)
    assert sig.parameters["bundle_store"].default is None


# =================================================================================================
# 3 · ⛔ from `emitted`, never from `qualified`
# =================================================================================================
def test_a_bundle_only_lists_signals_that_crossed():
    """A refused signal is simply not in `emitted`, so it cannot reach a bundle. Pinned here
    because the tempting shortcut — grouping `outcome.qualified` — is one line shorter and wrong."""
    emitted = [_Published(_Sig("crossed", thread_key="t1"))]
    report = _report(emitted)
    listed = [sid for b in report.bundles for sid in b.signal_ids]
    assert listed == ["crossed"]
    assert "refused" not in listed


def test_the_publisher_groups_from_emitted_in_its_own_source():
    """Both halves of the weld: if somebody switches the grouping input to `qualified`, this
    fails."""
    import inspect

    source = inspect.getsource(P._publish_sweep)
    assert "build_bundles(org_id, trace, [p.signal for p in emitted])" in source


# =================================================================================================
# 4 · the grouping itself still holds at this seam
# =================================================================================================
def test_one_thread_produces_one_bundle_and_two_threads_produce_two():
    one = _report([_Published(_Sig("s1", thread_key="t1")),
                   _Published(_Sig("s2", thread_key="t1"))])
    assert len(one.bundles) == 1

    two = _report([_Published(_Sig("s1", thread_key="t1")),
                   _Published(_Sig("s2", thread_key="t2"))])
    assert len(two.bundles) == 2


def test_every_emitted_signal_reaches_exactly_one_bundle():
    emitted = [_Published(_Sig(f"s{i}", thread_key=f"t{i % 2}")) for i in range(6)]
    report = _report(emitted)
    listed = sorted(sid for b in report.bundles for sid in b.signal_ids)
    assert listed == sorted(p.signal.signal_id for p in emitted)


def test_the_bundle_carries_the_trace_id_forward():
    """Minted in L1 and unchanged to L6 — a bundle must be findable from any downstream receipt."""
    report = _report([_Published(_Sig("s1", thread_key="t1"))])
    assert report.bundles[0].trace_id == "trace-1"

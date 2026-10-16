"""STEP-12 · a corpus `{baseline: …}` threshold reads the file's own measured normal on the compiled lane.

    .venv/bin/python -m pytest -q tests/reason/test_a_corpus_baseline_reads_the_files_numbers.py

Tree `yc2_w27_s12` M33.C1.L-logic.V0.U04, `03` F104. The corpus writes its silences against the
person's own rhythm — *"days since their last mail ≥ 2 × how often they write"*,
`{baseline: write_interval, mult: 2}` (92 uses across Sales, Admin and Support). `ContextAdapter`
reads that baseline from the slice's `metadata["baselines"]`, which only the legacy lane ever wrote, so
on the compiled lane every such threshold answered UNKNOWN. `expertise_capability_manifest` now takes
the file's measured numbers (`baselines`, each a `contracts.measured.Measured` with its n) and hands
the adapter every one that is a NORMAL — measured here, on enough observations (`06` D37); a sparse
number is never a habit, so it still answers UNKNOWN, and a slice that carries its own baselines keeps
them.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from genios_engine.contracts.measured import NORMAL_AT, PLAYBOOK_PRIOR, Measured
from genios_engine.packs.compiler.context_adapter import ContextAdapter, PredicateState
from genios_engine.reason.adapters import expertise as E
from tests.packs.compiler.l3_inputs import NOW, build_situation, build_slice

pytestmark = pytest.mark.unit

QUIET_TEN_DAYS = {"thread.last_inbound": {"value": (NOW - timedelta(days=10)).isoformat()}}
#: "Ten days quiet is past twice how often they write" — the corpus's own shape.
PAST_TWICE_THEIR_RHYTHM = {"fn": "days_since", "path": "thread.last_inbound", "op": ">=",
                           "value": {"baseline": "write_interval", "mult": 2}}


def _verdict(baselines=None, *, metadata=None):
    context = build_slice(facts=QUIET_TEN_DAYS, metadata=metadata)
    return ContextAdapter(build_situation(), E.with_file_baselines(context, baselines)).evaluate(
        PAST_TWICE_THEIR_RHYTHM)


def _measured(value, n, **kw):
    return Measured(value=value, n=n, basis="person", unit="days", **kw)


def test_without_the_files_numbers_the_threshold_cannot_be_answered():
    verdict = _verdict()
    assert verdict.state is PredicateState.UNKNOWN and "baseline:write_interval" in verdict.missing


@pytest.mark.parametrize("rhythm, state", [(3.0, PredicateState.TRUE), (6.0, PredicateState.FALSE)])
def test_a_normal_measured_on_the_file_answers_the_threshold(rhythm, state):
    """Writes every three days: ten quiet days is past twice that. Every six: it is not."""
    assert _verdict({"write_interval": _measured(rhythm, NORMAL_AT)}).state is state


def test_a_sparse_number_is_never_a_habit_and_still_answers_unknown():
    assert _verdict({"write_interval": _measured(3.0, NORMAL_AT - 1)}).state is PredicateState.UNKNOWN


def test_a_prior_is_no_measurement_of_this_file():
    prior = Measured(value=3.0, n=NORMAL_AT, basis="playbook", unit="days", source=PLAYBOOK_PRIOR)
    assert _verdict({"write_interval": prior}).state is PredicateState.UNKNOWN


def test_a_slice_that_carries_its_own_baselines_keeps_them():
    """The legacy lane's slice already carries what it read; the file's numbers never overwrite it."""
    kept = _verdict({"write_interval": _measured(3.0, NORMAL_AT)},
                    metadata={"baselines": {"write_interval": Decimal("6.0")}})
    assert kept.state is PredicateState.FALSE


def test_nothing_handed_leaves_the_slice_as_it_was():
    """A slice is content-addressed and its metadata is part of the address: nothing to hand, nothing
    changes — the same object comes back."""
    context = build_slice(facts=QUIET_TEN_DAYS)
    assert E.with_file_baselines(context, None) is context
    assert E.with_file_baselines(context, {"write_interval": _measured(3.0, 1)}) is context


class _StoppedAtTheWeld(Exception):
    """Raised where the weld would run: the test needs only what was built before it."""


def _stop_at_the_weld(*_args, **_kwargs):
    raise _StoppedAtTheWeld()


def test_the_manifest_hands_them_to_the_adapter_it_binds_with(monkeypatch):
    """`expertise_capability_manifest(…, baselines=…)` is the seam the compiled lane calls; the adapter
    the weld binds with is built over the slice the file's numbers were handed to."""
    seen = []

    class _Adapter(ContextAdapter):
        def __init__(self, situation, context=None):
            seen.append(context)
            super().__init__(situation, context)
    monkeypatch.setattr(E, "ContextAdapter", _Adapter)
    monkeypatch.setattr(E, "_plays", lambda package: ((), {}, {}))
    # ⛔ Was a generator `.throw(StopIteration())`: on Python 3.11 — CI's and production's (`Dockerfile`) — a
    # StopIteration thrown into a generator surfaces as `RuntimeError: generator raised StopIteration` (PEP 479),
    # on 3.13 (the local venv) as itself, so the test passed here and failed in CI (run 38514247292). A plain
    # exception of the test's own says the same thing on every version.
    monkeypatch.setattr(E, "weld_package", _stop_at_the_weld)
    with pytest.raises(_StoppedAtTheWeld):
        E.expertise_capability_manifest(
            SimpleNamespace(metadata={}), root_entity_type="account",
            situation=build_situation(), context=build_slice(facts=QUIET_TEN_DAYS),
            baselines={"write_interval": _measured(3.0, NORMAL_AT)})
    assert seen and seen[0].metadata["baselines"] == {"write_interval": Decimal("3.0")}

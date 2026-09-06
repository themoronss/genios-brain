"""H6 · MAX_PASSES actually BOUNDS THE DRAIN — proven by making a derivation oscillate.

`test_convergence.py` proves the arithmetic on `_record_convergence` (where the three inputs can
be stated rather than arranged) and proves the wiring on a sweep that CONVERGES. Neither of those
is the gate row. Doc 09 asks for *drains exceeding `MAX_PASSES` — 0*, and doc 13 asks for a
bounded fixpoint over a derivation that does not settle; a guard that has only ever been shown a
settling tenant has not been shown to bound anything.

So this file installs a derivation that genuinely will not settle — a pass inside `process_pending`
that flips a lifecycle state on every sweep, which is precisely doc 13's L-4 shape (a derived
state feeding a re-derivation) — and drives the REAL drain over it. The assertions are that the
counter climbs, that it stops at three, that the alert carries the receipt doc 13 asks for, and,
the one that makes the bound worth having, that the drain still RETURNS: an unbounded fixpoint's
symptom is "a slow sweep, then a slower one", not an exception.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy import text

from genios_engine.context.runner import MAX_PASSES, MAX_UNCONVERGED_REPORTED

from .test_convergence import EVAL_TIME, _cleanup, _reset, _situation

ORG = "org_h6_oscillation"

#: How many sweeps the oscillation test drives. A literal, for the reason spelled out at its use.
_SWEEPS = 4


@pytest.mark.pg
def test_an_oscillating_derivation_is_bounded_at_three_passes(pg_store, monkeypatch, caplog):
    """A derivation that never settles is stopped at `MAX_PASSES`, loudly, and the sweep returns."""
    from genios_engine.context import runner as R
    from genios_engine.platform.config import get_settings

    _reset(pg_store, ORG)
    try:
        _situation(pg_store, ORG, "sit_flip", status="active")

        # THE OSCILLATION. A pass the drain runs unconditionally, rewritten to flip the situation's
        # lifecycle state every sweep — a derived state that changes because it changed. It is
        # installed where M-4's block sits because that block is unconditional and lands between
        # the two fingerprints, which is exactly where doc 13's cycle would express itself.
        flips = {"n": 0}

        def _oscillate(store, org_id, **kw):
            flips["n"] += 1
            nxt = "dormant" if flips["n"] % 2 else "active"
            with store.engine.begin() as c:
                c.execute(text("update context_situations set status=:s where org_id=:o"),
                          {"s": nxt, "o": org_id})

            class _Sweep:
                @staticmethod
                def as_record():
                    return {}
            return _Sweep()

        monkeypatch.setattr("genios_engine.context.lifecycle.detect_resolutions", _oscillate)

        key = get_settings().crypto_key
        seen = []
        # A LITERAL BOUND, not `MAX_PASSES + 1`. A test that loops on the constant it is asserting
        # about HANGS when that constant is raised, and a hang reads as "inconclusive" in a
        # mutation run rather than as the failure it is. `_SWEEPS` is checked against MAX_PASSES
        # below so the two cannot drift apart silently.
        assert _SWEEPS == MAX_PASSES + 1, "the sweep count no longer brackets MAX_PASSES"
        with caplog.at_level(logging.ERROR, logger="genios.l2"):
            for _ in range(_SWEEPS):
                out = R.process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key,
                                        eval_time=EVAL_TIME)
                assert out["processed"] == 0, "no events: every move is the fixpoint's own"
                seen.append(out["convergence"])

        # EVERY sweep moves the state with nothing ingested, including the first: the oscillator
        # runs before the closing fingerprint is taken. So the counter climbs from one and the
        # breach is raised on the third — `MAX_PASSES` is where the ALERT fires, not where the
        # counting stops.
        passes = [e.get("passes") for e in seen]
        assert passes == [1, 2, MAX_PASSES, MAX_PASSES + 1], passes
        assert [e.get("exceeded") for e in seen] == [False, False, True, True], seen

        # AND THE DRAIN KEEPS DRAINING. Doc 13: *"Do NOT keep iterating. Publish what pass 3
        # produced."* Across sweeps that means the breach is raised and the sweep completes — it
        # does not mean the tenant stops being ingested. A guard that could halt a drain over a
        # derived-view defect would be a worse failure than the loop it watches for, so the
        # assertion is that the pass ran on every sweep and every call RETURNED.
        assert flips["n"] == _SWEEPS, flips
        assert all(e.get("checked") for e in seen)

        # THE ALERT, not a log line — doc 13's own words, and the name has to be greppable.
        assert any("l2_convergence_exceeded" in r.getMessage() for r in caplog.records), (
            "the breach was never raised as an alert")

        with pg_store.engine.connect() as c:
            row = c.execute(text("select passes, exceeded_at, detail from l2_convergence "
                                 "where org_id=:o"), {"o": ORG}).first()
        assert row.passes >= MAX_PASSES and row.exceeded_at is not None
        assert row.detail["max_passes"] == MAX_PASSES
        assert row.detail["state_hash_before"] != row.detail["state_hash_after"]
        assert len(row.detail["situations_still_changing"]) <= MAX_UNCONVERGED_REPORTED
    finally:
        _cleanup(pg_store, ORG)


@pytest.mark.pg
def test_the_bound_releases_when_the_derivation_settles(pg_store, monkeypatch):
    """A ratchet that never releases would make `exceeded_at` mean "breached once, in 2024".

    Without this the test above passes on a guard that latches on the first breach and never
    clears, which would be indistinguishable from a working bound for exactly as long as nobody
    fixed the cycle.
    """
    from genios_engine.context import runner as R
    from genios_engine.platform.config import get_settings

    _reset(pg_store, ORG)
    try:
        _situation(pg_store, ORG, "sit_flip", status="active")
        moving = {"on": True, "n": 0}

        def _maybe_oscillate(store, org_id, **kw):
            if moving["on"]:
                moving["n"] += 1
                with store.engine.begin() as c:
                    c.execute(text("update context_situations set status=:s where org_id=:o"),
                              {"s": "dormant" if moving["n"] % 2 else "active", "o": org_id})

            class _Sweep:
                @staticmethod
                def as_record():
                    return {}
            return _Sweep()

        monkeypatch.setattr("genios_engine.context.lifecycle.detect_resolutions", _maybe_oscillate)
        key = get_settings().crypto_key
        for _ in range(_SWEEPS):
            out = R.process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key,
                                    eval_time=EVAL_TIME)
        assert out["convergence"]["exceeded"] is True

        moving["on"] = False                                   # the cycle is fixed
        out = R.process_pending(org_id=ORG, store=pg_store, llm=None, crypto_key=key,
                                eval_time=EVAL_TIME)
        assert out["convergence"]["converged"] is True
        assert out["convergence"]["passes"] == 0
        assert out["convergence"]["exceeded"] is False
        with pg_store.engine.connect() as c:
            row = c.execute(text("select passes, exceeded_at from l2_convergence where org_id=:o"),
                            {"o": ORG}).first()
        assert row.passes == 0 and row.exceeded_at is None, (
            "a standing breach outlived the cycle that caused it")
    finally:
        _cleanup(pg_store, ORG)


def test_max_passes_is_a_small_bound_and_not_merely_a_number():
    """Doc 13's `MAX_PASSES = 3`, asserted so that RAISING it fails rather than hangs.

    Every other test of this bound drives it by looping `range(MAX_PASSES)`, which is the readable
    way to write it and means a mutation that raises the constant sends those tests into a loop.
    A hang is not a red test — in a mutation run it reports as inconclusive, which is exactly how
    a bound with no real coverage looks. Two assertions, neither of which can loop.
    """
    assert MAX_PASSES == 3, (
        "doc 13 fixes the bounded fixpoint at three passes; the number moved without the doc")
    assert 1 < MAX_PASSES <= 5, (
        f"MAX_PASSES = {MAX_PASSES} is not a bound. Doc 13's whole argument is that an unbounded "
        "sweep 'does not obviously not terminate — it looks like a slow sweep, then a slower "
        "one', and a ceiling large enough to never be reached is the unbounded case wearing a "
        "constant's name")

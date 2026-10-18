r"""The recall guard runs on a pass, and two of its siblings correctly never will.

⛔ WHAT WAS WRONG. `deliver/lane_recall.py` was built on 2026-09-30 as M13 `STEP-02` — *"prove
nothing died quietly"* — with 24 tests and a full green suite. **Nothing in the engine imported it.**
Three files mentioned it and all three were comments, and the worst of them, `pipeline.py:516`, was
*reasoning about `recall_verdict`'s correctness*: explaining that the lane is tallied at the two
sites where a card is WRITTEN so that the tally and the comparison are incremented by different
lines, "the only version of this check worth having".

> ⛔ The code was designed around a verdict nobody computed. **A comment that reasons about a
> guard's correctness is not evidence the guard runs.**

Ninth instance of built-tested-green-and-called-by-nothing in this programme, and the second of its
own making: the unit that closed *"a lane nothing reads"* produced *"a guard nothing calls"*.

⛔ AND MY FIRST DIAGNOSIS WAS WRONG ABOUT TWO OF THE THREE. `low_confidence_is_never_silent` takes
no data but a default `floor_bp`; `every_lane_is_visible_or_deliberately_silent` takes **no
arguments at all**. `lane_recall.py`'s own header says the module is *"PURE. No I/O, no clock, no
model."* Those two ask questions about CODE — answerable at build time, identical on every run — so
their test callers are the correct and only ones. **A function that takes no data cannot be
measuring production**, and filing it as an unwired defect would have led to wiring a settled
question into a per-org tick.

⛔ IT MAY NEVER RAISE. This file's own rule, written for `collapse_unmeasured`: *"a receipt that can
abort the thing it is a receipt for turns an accounting failure into a product failure."* An
unbalanced tally means cards went somewhere nobody is looking; dropping the pass over it means they
went nowhere at all.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

from genios_engine.deliver import delivery_health as H
from genios_engine.deliver import pipeline
from genios_engine.deliver.lane_display import TALLY_KEYS
from genios_engine.deliver.lane_recall import RecallVerdict, recall_verdict

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _pass(monkeypatch, signals: list[dict], *, store=None):
    """One real `build_cards_for_org` pass, with the signal read stubbed."""
    monkeypatch.setattr(pipeline, "ensure_default", lambda *_a: None)
    monkeypatch.setattr(pipeline, "_open_signals_without_cards", lambda *_a: signals)
    store = store or SimpleNamespace(claim_build=lambda *_a, **_k: None)
    return pipeline.build_cards_for_org(
        graph=object(), card_store=store, org_id="org_1", registry=object(), eval_time=NOW)


# ---------------------------------------------------------------------------------------------
# it runs
# ---------------------------------------------------------------------------------------------

def test_a_pass_computes_a_recall_verdict(monkeypatch) -> None:
    """The whole point of the step."""
    out = _pass(monkeypatch, [])
    assert "lane_recall" in out, "the pass produced no recall verdict"
    assert out["lane_recall_balanced"] is True


def test_the_guard_runs_even_when_the_pass_builds_nothing(monkeypatch) -> None:
    """⛔ An empty pass is exactly when a silent drop hides: zero built and zero counted agree, so
    a guard that only runs when cards exist would never see the pass where everything vanished."""
    out = _pass(monkeypatch, [])
    assert out.get("built", 0) == 0
    assert "lane_recall" in out


def test_the_guard_runs_when_the_pass_cannot_claim_a_lease(monkeypatch) -> None:
    """A refused build lease is an early path through the loop, and it still reaches the verdict."""
    out = _pass(monkeypatch, [{"signal_id": "sig_1", "effective_config": {}}])
    assert out["build_in_progress"] == 1
    assert "lane_recall" in out


# ---------------------------------------------------------------------------------------------
# ⛔ it is acted on, and it never kills the pass
# ---------------------------------------------------------------------------------------------

def test_the_verdict_is_acted_on_and_not_discarded() -> None:
    """⛔ THE REAL RISK OF THIS STEP, and the mutation that survived fifteen tests in L4: a value
    computed and dropped. Read from the AST, with the docstring excluded BY IDENTITY (the first
    statement) rather than by value -- `ast.get_docstring()` returns cleaned text while the node
    holds raw, so excluding by value lets prose through.
    """
    tree = ast.parse(inspect.getsource(pipeline.build_cards_for_org).lstrip())
    body = tree.body[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    called = {n.func.id for stmt in body for n in ast.walk(stmt)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "recall_verdict" in called, "the pass never calls the guard"

    # and the result reaches `out`, rather than being computed into a dead local
    written = {n.slice.value for stmt in body for n in ast.walk(stmt)
               if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
               and n.value.id == "out" and isinstance(n.slice, ast.Constant)
               and isinstance(n.slice.value, str)}
    assert "lane_recall" in written and "lane_recall_balanced" in written, (
        f"the verdict is computed and not recorded; out keys written: {sorted(written)}")


def test_an_unbalanced_tally_is_recorded_and_the_pass_still_returns(monkeypatch) -> None:
    """⛔ *A receipt that can abort the thing it is a receipt for turns an accounting failure into a
    product failure.*

    ⛔ THE LAST ASSERTION WAS ADDED AFTER A MUTATION SURVIVED. Making the guard `raise` on an
    unbalanced verdict left this test GREEN, because the raise lands inside the `try` that exists to
    stop a broken measurement killing the pass — so the pass's own safety net swallowed a defect in
    the half that ACTS on the verdict. The two outcomes became indistinguishable from outside.

    **"I could not measure this" and "I measured it and it is wrong" are different sentences**, and
    a guard that cannot tell them apart has one state where it should have two. That is the same
    rule `collapse_unmeasured` was written for, applied to the flag rather than the count.
    """
    monkeypatch.setattr(pipeline, "recall_verdict",
                        lambda _c: RecallVerdict(cards_built=7, cards_accounted=4))
    out = _pass(monkeypatch, [])
    assert out["lane_recall_balanced"] is False
    assert "3 unaccounted for" in out["lane_recall"]
    assert "lane_recall_unmeasured" not in out, (
        "an unbalanced verdict was reported as an unmeasurable one -- something in the acting half "
        "raised and the measurement guard caught it")


def test_a_guard_that_cannot_measure_itself_says_so(monkeypatch) -> None:
    """⛔ The same rule as `collapse_unmeasured`: a pass that could not measure itself must not look
    identical to one that measured zero -- *the invisible refusal L2-0 spent a whole step on.*"""
    def boom(_counts):
        raise RuntimeError("no tallies")
    monkeypatch.setattr(pipeline, "recall_verdict", boom)
    out = _pass(monkeypatch, [])
    assert out["lane_recall_unmeasured"] == 1
    assert "lane_recall_balanced" not in out, (
        "a failed measurement must not leave a verdict behind")


# ---------------------------------------------------------------------------------------------
# the verdict itself, on seeded losses
# ---------------------------------------------------------------------------------------------

def test_a_dropped_card_makes_the_verdict_fail() -> None:
    """⛔ A guard that cannot go red on a real miss is decoration."""
    base = {k: 0 for k in TALLY_KEYS}
    assert recall_verdict(dict(base, built=3, refreshed=1,
                               cards_output_lane_decision=4)).balanced
    lost = recall_verdict(dict(base, built=3, refreshed=1, cards_output_lane_decision=2))
    assert not lost.balanced and "2 unaccounted for" in lost.explain()


def test_a_refresh_counts_as_built_and_a_pass_that_only_refreshes_balances() -> None:
    """⛔ `built` + `refreshed`, NOT `built` alone -- `recall_verdict`'s own docstring: an earlier
    reading would have reported a loss on every pass that improved an existing card, *"and the
    'fix' for a false alarm is always to loosen the check."*"""
    base = {k: 0 for k in TALLY_KEYS}
    assert recall_verdict(dict(base, built=0, refreshed=2,
                               cards_output_lane_monitor=2)).balanced


def test_an_undeclared_lane_key_is_a_failure_not_a_zero() -> None:
    """*"`pipeline` zeroes all six on purpose, so a missing key means somebody stopped declaring
    one."*"""
    v = recall_verdict({"built": 1, "cards_output_lane_decision": 1})
    assert not v.balanced and "never declared" in v.explain()


# ---------------------------------------------------------------------------------------------
# ⛔ the declaration, both directions
# ---------------------------------------------------------------------------------------------

def test_the_declaration_no_longer_claims_recall_verdict_is_unwired() -> None:
    """L4 deleted `monitor.blocking_action` from `UNREACHED` the moment it was wired; the entry
    left behind is the lie, not the call."""
    assert "lane_recall.recall_verdict" not in H.KNOWN_UNWIRED
    assert "lane_recall.recall_verdict" not in H.DECLARED
    assert H.now_called() == (), f"a declared entry has acquired a caller: {H.now_called()}"


def test_the_two_property_guards_are_declared_and_must_stay_unwired() -> None:
    """⛔ THE CORRECTION. Both take no production data, so wiring either would re-derive the same
    answer about unchanged code on every org on every tick."""
    for name in ("lane_recall.low_confidence_is_never_silent",
                 "lane_recall.every_lane_is_visible_or_deliberately_silent"):
        assert name in H.UNREACHED, f"{name} is a build-time guard, not a defect"
        assert name not in H.KNOWN_UNWIRED
    counts = __import__("genios_engine.executive.unreached", fromlist=["x"]).qualified_call_counts(
        H.engine_sources())
    assert counts.get(("lane_recall", "low_confidence_is_never_silent"), 0) == 0
    assert counts.get(("lane_recall", "every_lane_is_visible_or_deliberately_silent"), 0) == 0


def test_the_module_is_no_longer_an_orphan() -> None:
    """⛔ Three files mentioned `lane_recall` and all three were comments. One now imports it."""
    counts = __import__("genios_engine.executive.unreached", fromlist=["x"]).qualified_call_counts(
        H.engine_sources())
    assert counts.get(("lane_recall", "recall_verdict"), 0) > 0

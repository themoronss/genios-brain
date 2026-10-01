"""Who produces the OBJECT, and who produces the EVIDENCE for it.

    pytest tests/test_object_placement.py -q

Four objects sat in four different places and the question *"should Layer 1 build this?"* was
re-argued every time one of them came up. `docs/LAYER_MAP.md` now answers it once:

> **`capture/` produces the EVIDENCE. `context/` produces the OBJECT.
> The VOCABULARY both use lives in `contracts/`.**

⛔ THESE TESTS ARE GUARDS, NOT A MIGRATION. Every assertion below already holds. Their whole job is
to fail the day somebody moves a producer, and to fail *saying which rule was broken* — because the
two reasons this rule exists are not obvious from the diff that would break it:

  1. **An object needs the graph; evidence does not.** `open_loop` has to know what the company
     already knows. A producer moved into `capture/` would have to import `context/` — upward, and
     `tests/test_layer_topology.py` already fails the build on that. So half of this rule is
     enforced by physics; these tests cover the half that is not.

  2. ⛔ **The condition split is load-bearing.** `parse_condition` refuses anything it cannot
     ground, and *that refusal is the queue the `condition_now_true` angle gates on*. Collapsing
     the split into one Layer 1 object would destroy the refusal queue — and with it the only thing
     stopping a rhetorical aside ("let's talk once things settle down") from becoming a predicate
     that eventually fires and nags somebody about a throwaway line. That loss would not show up as
     a failing test anywhere else, which is exactly why it is written down here.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_RULE = ("docs/LAYER_MAP.md: capture/ produces the EVIDENCE, context/ produces the OBJECT, "
         "and the vocabulary lives in contracts/.")


# =================================================================================================
# 1 · the VOCABULARY is cross-cutting — both layers may name the same thing
# =================================================================================================
def test_the_ask_vocabulary_is_in_contracts():
    """`ASK_KINDS` is shared: L1 extracts an ask, L3 decides it is still open. Neither owns the
    word, so it lives where both may import it."""
    from genios_engine.contracts import open_loop

    assert isinstance(open_loop.ASK_KINDS, frozenset) and open_loop.ASK_KINDS
    assert callable(open_loop.is_ask)


def test_the_commitment_vocabulary_is_in_contracts():
    from genios_engine.contracts.extraction import Commitment

    assert Commitment.__module__ == "genios_engine.contracts.extraction", _RULE


# =================================================================================================
# 2 · capture/ produces the EVIDENCE
# =================================================================================================
def test_layer_one_carries_the_condition_evidence_and_not_the_condition_object():
    """⛔ The split, pinned. L1 records the two things a sentence actually said — that it was
    conditional, and the words of the condition. It does NOT decide whether the condition is met;
    that needs the world, which L1 cannot see."""
    from genios_engine.contracts.extraction import Commitment

    fields = Commitment.model_fields
    assert "is_conditional" in fields, _RULE
    assert "condition_text" in fields, _RULE

    # And the evidence stays evidence: no verdict field creeps onto it.
    for verdict_ish in ("is_met", "satisfied", "verdict", "predicate"):
        assert verdict_ish not in fields, (
            f"Commitment gained {verdict_ish!r}. That is a JUDGEMENT about the world, and L1 "
            f"cannot see the world. " + _RULE)


def test_delivery_status_evidence_is_produced_in_capture():
    from genios_engine.capture import delivery_status

    assert delivery_status.__name__.startswith("genios_engine.capture."), _RULE


# =================================================================================================
# 3 · context/ produces the OBJECT
# =================================================================================================
@pytest.mark.parametrize(("dotted", "symbol"), [
    ("genios_engine.context.correlation_timeline", "DormantCondition"),
    ("genios_engine.context.correlation_timeline", "parse_condition"),
])
def test_the_condition_object_is_produced_in_context(dotted, symbol):
    import importlib

    module = importlib.import_module(dotted)
    assert hasattr(module, symbol), f"{symbol} left {dotted}. " + _RULE
    obj = getattr(module, symbol)
    assert getattr(obj, "__module__", dotted) == dotted, _RULE


@pytest.mark.parametrize("dotted", [
    "genios_engine.context.open_loops",      # open question
    "genios_engine.context.waiting",         # who is still owed an answer
    "genios_engine.context.meeting_touch",   # meeting follow-up
])
def test_the_object_producers_live_in_context(dotted):
    import importlib

    module = importlib.import_module(dotted)
    assert module.__name__ == dotted, _RULE


# =================================================================================================
# 4 · ⛔ and capture/ never grows its own copy of one
# =================================================================================================
@pytest.mark.parametrize("forbidden", ["DormantCondition", "class OpenLoop", "def close_loop"])
def test_capture_does_not_define_an_object_producer(forbidden):
    """The half the topology test cannot catch. `capture/` importing `context/` already fails the
    build; `capture/` DEFINING its own `DormantCondition` would not, and would silently fork the
    refusal queue."""
    hits = [p.relative_to(_ROOT) for p in (_ROOT / "genios_engine" / "capture").rglob("*.py")
            if forbidden in p.read_text(encoding="utf-8", errors="ignore")]
    assert not hits, (f"capture/ now defines {forbidden!r} in {hits}. " + _RULE)


# =================================================================================================
# 5 · the one that is genuinely missing stays DECLARED missing
# =================================================================================================
def test_thread_terminal_state_is_recorded_as_absent():
    """⛔ Thread terminal state exists at SIGNAL level (`esqe/lifecycle.py`) and nowhere at THREAD
    level. That is the one member of this family with no producer at all.

    An absence with no record is indistinguishable from an oversight — this repository's own rule.
    So the absence is declared in the layer map, and this test fails if somebody deletes the
    declaration without building the thing.
    """
    text = (_ROOT / "docs" / "LAYER_MAP.md").read_text(encoding="utf-8")
    assert "Thread terminal state exists at SIGNAL level" in text, (
        "The declared gap for thread terminal state was removed from docs/LAYER_MAP.md. Either it "
        "was built — in which case add its producer to this test — or the declaration must stay.")


def test_the_rule_itself_is_written_down():
    """Both halves of the weld: these tests are meaningless if the rule they enforce is not
    readable by the person whose diff they fail."""
    text = (_ROOT / "docs" / "LAYER_MAP.md").read_text(encoding="utf-8")
    assert "produces the EVIDENCE" in text and "produces the OBJECT" in text

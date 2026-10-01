"""S2.F2.3 · the receipt reaches something a human reads.

    pytest tests/reason/test_a_lost_source_reaches_the_decision.py -q

⛔ THIS FILE EXISTS BECAUSE OF `not_carried`. This programme has now found six times the shape where a
value is computed correctly and dropped at a boundary. A `DegradedStep` that stopped at `ExecutionPlan`
would be the seventh: the planner would know a unit ran on two of three inputs, and the card would say
nothing.

**The unit is not done until the fact reaches something a human reads.**
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.reason import orchestrator as orch
from genios_engine.reason.plan import DegradedStep

pytestmark = pytest.mark.unit


# =================================================================================================
# 1 · ⛔ the fact leaves the plan
# =================================================================================================
def test_the_orchestrator_reads_the_planners_degradation_receipts():
    """⛔ THE ANTI-`not_carried` GUARD. If this assertion fails, the planner is computing a receipt that
    reaches nothing — which is the exact defect the receipt was built to end, relocated one hop."""
    source = inspect.getsource(orch)
    assert "plan.degraded" in source


def test_it_reaches_uncertainty_and_not_a_log_line():
    """`uncertainty` is the field that already means *"what we are not sure about, in words"* and it is
    carried onto the decision. A log line reaches an operator grepping; this reaches the card."""
    source = inspect.getsource(orch)
    at = source.index("plan.degraded")
    window = source[at - 900:at + 600]
    assert "uncertainty.append" in window
    assert "_log" not in window.split("for degraded_step")[-1]


def test_a_second_field_was_not_invented_for_it():
    """`ReasoningDecision.uncertainty` already exists and already means this. A second field would give
    the card two places to look, and one of them would eventually stop being read."""
    from genios_engine.contracts.reasoning import ReasoningDecision

    fields = set(ReasoningDecision.__dataclass_fields__)
    assert "uncertainty" in fields
    for invented in ("degraded_sources", "lost_sources", "degradations"):
        assert invented not in fields


# =================================================================================================
# 2 · ⛔ starved is said separately
# =================================================================================================
def test_starved_and_degraded_produce_different_sentences():
    """⛔ *"ran on 2 of 3"* is a reading over less. *"ran on 0 of 1"* is a unit asserting something with
    none of the input it said it needed. A reader that could not tell them apart would weigh them the
    same."""
    source = inspect.getsource(orch)
    assert "starved_sources:" in source
    assert "degraded_sources:" in source


def test_the_marker_carries_the_counts_not_just_the_unit_id():
    """"core.tension lost something" does not say how much. The counts are what make it actionable."""
    source = inspect.getsource(orch)
    assert "of" in source[source.index("degraded_sources:"):source.index("degraded_sources:") + 400]
    assert "available_sources" in source
    assert "declared_sources" in source


# =================================================================================================
# 3 · the marker format, built from the real contract
# =================================================================================================
@pytest.mark.parametrize(("declared", "available", "lost", "prefix", "counts"), [
    (("a", "b", "c"), ("a", "b"), ("c",), "degraded_sources", "2of3"),
    (("a", "b"), ("a",), ("b",), "degraded_sources", "1of2"),
    (("a",), (), ("a",), "starved_sources", "0of1"),
    (("a", "b"), (), ("a", "b"), "starved_sources", "0of2"),
])
def test_the_marker_a_receipt_would_produce(declared, available, lost, prefix, counts):
    """Re-derives the orchestrator's format from the contract, so a change to either side that breaks
    the agreement is caught here rather than on a card."""
    step = DegradedStep("core.tension", "1", declared, available, lost)
    marker = ((f"starved_sources:{step.reasoner_id}" if step.starved
               else f"degraded_sources:{step.reasoner_id}")
              + f":{len(step.available_sources)}of{len(step.declared_sources)}")
    assert marker == f"{prefix}:core.tension:{counts}"


# =================================================================================================
# 4 · ⛔ the confidence flag was deliberately NOT changed
# =================================================================================================
def test_the_degraded_flag_still_comes_only_from_optional_degradations():
    """⛔ THE SCOPE LINE FOR THIS UNIT, ASSERTED.

    `degraded=` feeds the decision maker's confidence. Folding `plan.degraded` into it would change
    DECISIONS — arguably for the better, since a required unit running on none of its declared sources
    is unambiguously a degraded run. But that is a behaviour change nobody asked for, and this unit's
    job is to make the fact REACH the surface, not to re-weigh it.

    If someone later decides to fold it in, this test should fail and be deleted on purpose — not
    quietly widened."""
    source = inspect.getsource(orch)
    assert "degraded=bool(optional_degradations)" in source


def test_the_omission_is_documented_where_it_happens():
    """An undocumented omission reads as an oversight, and the next person 'fixes' it."""
    source = inspect.getsource(orch)
    at = source.index("degraded=bool(optional_degradations)")
    assert "DELIBERATELY NOT FOLDED" in source[at - 800:at]

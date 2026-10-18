"""STEP-13 · the LLM decider routes its lane, as the formula decider does.

    .venv/bin/python -m pytest -q tests/reason/test_the_llm_decider_routes_its_lane.py

Tree `yc2_w27_s13` M36.C1.L-logic.V0.U01 (`reason/llm_decision_maker.decide_with_llm`), `03` F10 and F186.
The formula decider routes its decision where the outcome and the confidence first exist together
(`reason/decision_maker`, by the pure `reason/output_lane.route`); the model's path built its decision with
no lane at all, so every signal it decided reached the card with a NULL lane. It now routes the same way —
from its outcome and its confidence, a conflict read off the uncertainty markers — and never from the
model: the lane is a route, and no model produces a route.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.reasoning import (CandidateCheck, CheckOutcome, DecisionOutcome,
                                               OutputLane)
from genios_engine.reason import llm_decision_maker as llm_dm
from genios_engine.reason.decision_maker import DecisionMaker
from genios_engine.reason.output_lane import route
from tests.reason.test_llm_decision_maker import FakeLLM, _answer, _request, _results

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    llm_dm._reset_for_tests()
    monkeypatch.setattr(llm_dm, "_record_cost", lambda **_kw: None)
    yield
    llm_dm._reset_for_tests()


def _decide(llm, *, uncertainty=(), results=None):
    return llm_dm.decide_with_llm(_request(), results or _results(), uncertainty=uncertainty,
                                  degraded=False, llm=llm).decision


@pytest.mark.parametrize("llm, outcome, lane", [
    (FakeLLM(_answer({"restore_momentum": 7_000}, confidence=7_000)), DecisionOutcome.DECISION,
     OutputLane.DECISION),
    (FakeLLM(_answer({"restore_momentum": 5_000}, confidence=3_200)), DecisionOutcome.DECISION,
     OutputLane.MONITOR),                                         # a move, under the 6,000 floor
    (FakeLLM(_answer({"restore_momentum": 4_000}, outcome="defer")), DecisionOutcome.DEFER,
     OutputLane.MONITOR),
    (None, DecisionOutcome.DEFER, OutputLane.MONITOR),            # no client: a deferral, said
])
def test_the_models_decision_carries_the_routers_lane(llm, outcome, lane):
    decision = _decide(llm)
    assert decision.outcome == outcome and decision.output_lane == lane
    expected = route(outcome=decision.outcome, confidence_bp=decision.confidence_bp)
    assert (decision.output_lane, decision.lane_reason) == (expected.lane, expected.reason)


def test_every_play_eliminated_is_routed_as_ours():
    check = CandidateCheck(play_id="restore_momentum", stage="policy", outcome=CheckOutcome.ELIMINATE,
                           reason_code="tenant_policy_block", evaluator_id="core.constraint",
                           evaluator_version="1")
    decision = _decide(FakeLLM(), results=_results(checks=(check,)))
    assert decision.outcome == DecisionOutcome.BLOCKED
    assert decision.output_lane == route(outcome=DecisionOutcome.BLOCKED, confidence_bp=0).lane
    assert decision.lane_reason


@pytest.mark.parametrize("marker", ["conflict_open:deal.stage", "cross_domain_contradiction:sales"])
def test_an_open_conflict_beats_a_confident_move_on_both_deciders(monkeypatch, marker):
    """The conflict is read off the same markers the formula decider reads — the two deciders cannot
    disagree about whether a conflict is open."""
    model = _decide(FakeLLM(_answer({"restore_momentum": 9_000}, confidence=9_000)), uncertainty=(marker,))
    assert model.output_lane == OutputLane.CONFLICT and model.lane_reason
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org: False)
    formula = DecisionMaker().decide(_request(), _results(), terminal=None, uncertainty=(marker,),
                                     degraded=False).decision
    assert formula.output_lane == model.output_lane == OutputLane.CONFLICT


def test_the_lane_is_never_the_models_to_give():
    """An answer that names a lane is no route: the router reads the outcome and the confidence."""
    answer = {**_answer({"restore_momentum": 7_000}, confidence=7_000), "output_lane": "suppress",
              "lane_reason": "the model said so"}
    decision = _decide(FakeLLM(answer))
    assert decision.output_lane == OutputLane.DECISION and "the model said so" not in decision.lane_reason

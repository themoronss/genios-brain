"""STEP-12 M33 · a run whose decision maker asks no model is read by no model either.

    .venv/bin/python -m pytest -q tests/reason/test_a_decision_that_asks_no_model_reads_none.py

Tree `yc2_w27_s12` M33.C1.L-logic.V1.U05 (`reason/orchestrator.py`). With the test-mode decider on
(`GENIOS_L4_LLM_DECISION_MAKER`), the orchestrator has R-1 read every run's ambiguity by model before it
reaches the decision maker, and runs it again on the augmented request. A covered file's decision is read
from a review the model already wrote (`reason/expert/decide.ExpertDecisionMaker`, `asks_no_model`): R-1's
readings would be read by nothing, paid for, and would move the snapshot the decision is replayed from. So
the orchestrator asks R-1 only before a decision maker that may consult a model — and the negative
control proves the switch would have fired on the same request with an ordinary decision maker.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.contracts.reasoning import DecisionOutcome
from genios_engine.reason import llm_decision_maker, llm_interpretation
from genios_engine.reason.expert import decide as D
from tests.reason.expert.checks import as_written
from genios_engine.reason.expert import store
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import ConstraintReasoner
from genios_engine.reason.registry import ReasonerRegistry

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
RAW = {
    "facts": [{"claim": "Neel wrote asking for a first call", "evidence": ["evt_neel_0927"]}],
    "frames": {"primary": "a first call with a fund", "rivals": ["an exploratory chat"]},
    "expected_vs_actual": {"stage": None, "expected": "a pre-read", "actual": "nothing sent"},
    "scenarios": {"do_nothing": "the call runs cold", "act": "a pre-read frames it", "best": "a meeting",
                  "worst": "a pass", "signals_to_watch": ["a reply"]},
    "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible", "reasons": ["close"]},
    "mode": "act",
    "next_move": {"who": "the founder", "what": "Send Neel a pre-read", "for_whom": "Neel", "by_when": None},
    "alternative": "send it after", "wait_or_stop": "raise it on the call", "done_when": "the call happens"}


def _request():
    row = store.StoredReview(
        file_id="node_neel", fingerprint="ffp-0123456789abcdef01234567", model="claude-sonnet-5",
        prompt_version="expert-review.v2", dossier_digest="d" * 64, status=store.VALID, reason=None,
        review=ExpertReview.from_mapping(RAW), raw=RAW, input_tokens=1, output_tokens=1,
        cost_micro_usd=1, reviewed_at=NOW, checked=as_written(ExpertReview.from_mapping(RAW)))
    return D.request_for(row, org_id="org_no_model", root_entity_type="company",
                         domain="founder_office", eval_time=NOW, graph_version=3)


@pytest.fixture
def r1_on(monkeypatch):
    """The test-mode decider switched on, and R-1's model read recorded rather than made."""
    asked = []
    monkeypatch.setattr(llm_decision_maker, "enabled_for", lambda org_id: True)
    monkeypatch.setattr(llm_decision_maker, "client", lambda: object())

    def _interpret(request, llm):
        asked.append(request.capability.capability_id)
        return request                                   # nothing to add: the run goes on as it was
    monkeypatch.setattr(llm_interpretation, "interpret_request", _interpret)
    return asked


def test_the_experts_run_asks_r1_nothing(r1_on):
    execution = D.decide(_request())
    assert r1_on == [], "R-1 read a run whose decision was the review's"
    assert execution.decision.outcome == DecisionOutcome.DECISION


def test_without_the_switch_the_same_run_would_have_asked_r1(r1_on, monkeypatch):
    """⛔ THE NEGATIVE CONTROL: the same request, an orchestrator whose decision maker does not say it
    asks no model — R-1 is asked, as it is on every other run in test mode."""
    monkeypatch.setattr(D.ExpertDecisionMaker, "asks_no_model", False)
    ReasoningOrchestrator(ReasonerRegistry((D.ReviewReader(), ConstraintReasoner())),
                          decision_maker=D.ExpertDecisionMaker()).execute(_request())
    assert r1_on == [D.CAPABILITY_ID]


def test_an_ordinary_decision_maker_is_read_by_r1_as_before(r1_on, monkeypatch):
    """A decision maker that says nothing about asking — every one but the expert's — is read by R-1
    in test mode exactly as before: the switch is opt-in, never a default."""
    from genios_engine.reason.decision_maker import DecisionMaker

    class _Decided(Exception):
        pass

    def _decide(*_a, **_k):
        raise _Decided()
    monkeypatch.setattr(llm_decision_maker, "decide_with_llm", _decide)
    with pytest.raises(_Decided):
        ReasoningOrchestrator(ReasonerRegistry((D.ReviewReader(), ConstraintReasoner())),
                              decision_maker=DecisionMaker()).execute(_request())
    assert r1_on == [D.CAPABILITY_ID], "R-1 was not asked before an ordinary decision maker"

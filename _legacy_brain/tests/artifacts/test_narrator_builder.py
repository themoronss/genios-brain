"""Tests for narrator + builder. Uses FAKE LLM (no real API calls)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.artifacts.builder import ArtifactKind, build_artifact
from core.artifacts.narrator import NarratorRejected, narrate
from core.artifacts.trace import AsOfPin, ConfidenceBreakdown, RuleFiringRef, SourceFactRef, Trace
from core.artifacts.uncertainty import UncertaintyFlag, UncertaintyKind
from core.foundations.db import Base
from core.graph.store import FactRow
from core.neural.client import LLMCall, LLMResponse


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class _FakeLLM:
    """Returns a fixed sequence of responses (one per call)."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[LLMCall] = []

    def call(self, call: LLMCall) -> LLMResponse:
        self.calls.append(call)
        if not self._responses:
            raise RuntimeError("FakeLLM out of responses")
        text = self._responses.pop(0)
        return LLMResponse(
            text=text,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0001,
            model_id="test",
            latency_ms=5,
        )


def _seed_fact(session: Session) -> str:
    fact = FactRow(
        org_id="o",
        subject="acme",
        predicate="usage_dropped",
        object="40pct",
        source_item_id="mem_1",
        asserted_by_type="source",
        asserted_by_id="mem_1",
        confidence=1.0,
        created_at=datetime.now(UTC),
    )
    session.add(fact)
    session.flush()
    return fact.id


def _make_trace(fact_id: str) -> Trace:
    return Trace(
        decision_id="dec_1",
        org_id="o",
        source_facts=[
            SourceFactRef(
                id=fact_id,
                subject="acme",
                predicate="usage_dropped",
                object="40pct",
                source_item_id="mem_1",
            )
        ],
        rules_fired=[
            RuleFiringRef(
                id="churn_usage_silence",
                priority=80,
                matched_facts={"usage_drop_pct_30d": 40},
                conclusion="churn_risk_high",
            )
        ],
        graph_path=[],
        confidence=ConfidenceBreakdown(overall=0.85, breakdown={"grounding": 1.0, "symbolic": 1.0}),
        uncertainty=[],
        as_of=AsOfPin(graph_version=10, timestamp=datetime(2026, 6, 1, tzinfo=UTC)),
    )


# ── narrator ───────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_narrator_grounded_output_accepted(session: Session) -> None:
    """Narrator output tight to fact tokens -> grounded -> returned.

    The grounding verifier is CONSERVATIVE BY DESIGN (per MD): every significant
    token must appear in some FactRow. Real narrator must stay tight to fact
    vocabulary; descriptive filler like 'based on the proof tree' gets rejected.
    """
    fact_id = _seed_fact(session)
    trace = _make_trace(fact_id)
    llm = _FakeLLM(["Acme usage_dropped 40pct."])
    result = narrate(session, trace=trace, llm=llm)  # type: ignore[arg-type]
    assert result.attempts == 1
    assert "acme" in result.prose.lower()


@pytest.mark.unit
def test_narrator_ungrounded_invents_number_rejected(session: Session) -> None:
    """LLM invents a number not in the fact -> ALL retries fail -> NarratorRejected.

    The fake LLM returns invented numbers on every retry — narrator gives up.
    """
    fact_id = _seed_fact(session)
    trace = _make_trace(fact_id)
    bad_responses = [
        "Acme value at $80000 per the proof tree.",
        "Acme value at $99999 per the proof tree.",
        "Acme value at $123456 per the proof tree.",
    ]
    llm = _FakeLLM(bad_responses)
    with pytest.raises(NarratorRejected):
        narrate(session, trace=trace, llm=llm)  # type: ignore[arg-type]


@pytest.mark.unit
def test_narrator_insufficient_proof_self_refusal(session: Session) -> None:
    """LLM says INSUFFICIENT_PROOF on every retry -> NarratorRejected."""
    fact_id = _seed_fact(session)
    trace = _make_trace(fact_id)
    llm = _FakeLLM(["INSUFFICIENT_PROOF", "INSUFFICIENT_PROOF", "INSUFFICIENT_PROOF"])
    with pytest.raises(NarratorRejected):
        narrate(session, trace=trace, llm=llm)  # type: ignore[arg-type]


# ── builder ────────────────────────────────────────────────────────────────


_SIMPLE_TEMPLATE = """# {{ title }}

{{ narrative }}

Confidence: {{ "%.0f"|format(confidence * 100) }}%

## Uncertainty
{{ uncertainty_summary }}

## Counterfactuals
{% if counterfactuals %}
{% for c in counterfactuals %}
- {{ c.kind }}: {{ c.get('disclaimer', 'no disclaimer') }}
{% endfor %}
{% else %}
None.
{% endif %}

asOf: v{{ as_of_version }} ({{ as_of_timestamp }})
"""


@pytest.mark.unit
def test_builder_renders_with_trace_and_narrator(session: Session) -> None:
    fact_id = _seed_fact(session)
    trace = _make_trace(fact_id)
    llm = _FakeLLM(["Acme usage_dropped 40pct."])
    narrator_result = narrate(session, trace=trace, llm=llm)  # type: ignore[arg-type]

    artifact = build_artifact(
        org_id="o",
        decision_id="dec_1",
        kind=ArtifactKind.BRIEF,
        trace=trace,
        narrator_result=narrator_result,
        template_str=_SIMPLE_TEMPLATE,
        title="Acme — Churn Brief",
    )

    assert "Acme — Churn Brief" in artifact.body
    assert "Acme usage_dropped" in artifact.body
    assert "85%" in artifact.body
    assert "v10" in artifact.body  # as_of_version surfaced
    assert artifact.trace == trace
    assert artifact.counterfactuals == []


@pytest.mark.unit
def test_builder_propagates_uncertainty_summary(session: Session) -> None:
    fact_id = _seed_fact(session)
    trace = _make_trace(fact_id)
    # Add an uncertainty flag — must surface in summary
    trace_with_flag = trace.model_copy(
        update={
            "uncertainty": [
                UncertaintyFlag(
                    kind=UncertaintyKind.LLM_GAP_FILL,
                    target="conclusion",
                    severity="high",
                    detail="Part of conclusion from LLM gap-fill.",
                )
            ]
        }
    )
    llm = _FakeLLM(["Acme usage dropped 40pct."])
    narrator_result = narrate(session, trace=trace_with_flag, llm=llm)  # type: ignore[arg-type]

    artifact = build_artifact(
        org_id="o",
        decision_id="dec_1",
        kind=ArtifactKind.BRIEF,
        trace=trace_with_flag,
        narrator_result=narrator_result,
        template_str=_SIMPLE_TEMPLATE,
        title="x",
    )
    assert "llm_gap_fill" in artifact.body.lower()
    assert "1 uncertainty flag" in artifact.uncertainty_summary.lower()

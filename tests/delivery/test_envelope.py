"""Tests for core.delivery.envelope — the no-naked-output gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.delivery.bands import ConfidenceBand
from core.delivery.envelope import (
    Envelope,
    EnvelopeRoute,
    NakedOutputError,
    build_envelope,
)


def _now() -> datetime:
    return datetime(2026, 6, 1, tzinfo=UTC)


def _kwargs(**overrides):
    base = {
        "org_id": "o",
        "decision_id": "dec_1",
        "recommendation": {"conclusion": "churn_risk_high", "recommend": "follow_up"},
        "confidence": 0.85,
        "derivation": [{"rule_id": "r1", "conclusion": "churn_risk_high"}],
        "uncertainty": [],
        "route": "notify",
        "triggered_by": "query",
        "as_of_version": 42,
        "as_of_timestamp": _now(),
    }
    base.update(overrides)
    return base


# ── happy path ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_build_envelope_happy_path() -> None:
    env = build_envelope(**_kwargs())
    assert env.org_id == "o"
    assert env.decision_id == "dec_1"
    # 0.85 >= theta_act (0.75) -> the customer-facing band is "high".
    # The raw float is intentionally NOT on the envelope (stays internal).
    assert env.confidence == ConfidenceBand.HIGH
    assert env.route == EnvelopeRoute.NOTIFY
    assert env.as_of.graph_version == 42


# ── naked-output rejections ───────────────────────────────────────────────


@pytest.mark.unit
def test_recommendation_required() -> None:
    with pytest.raises(NakedOutputError, match="recommendation"):
        build_envelope(**_kwargs(recommendation=None))


@pytest.mark.unit
def test_derivation_required() -> None:
    with pytest.raises(NakedOutputError, match="derivation"):
        build_envelope(**_kwargs(derivation=None))


@pytest.mark.unit
def test_uncertainty_required_even_if_empty_list_ok() -> None:
    with pytest.raises(NakedOutputError, match="uncertainty"):
        build_envelope(**_kwargs(uncertainty=None))
    # Empty list is fine — field is REQUIRED but can be empty
    env = build_envelope(**_kwargs(uncertainty=[]))
    assert env.uncertainty == []


@pytest.mark.unit
def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(NakedOutputError):
        build_envelope(**_kwargs(confidence=1.5))


@pytest.mark.unit
def test_invalid_route_rejected() -> None:
    with pytest.raises(NakedOutputError):
        build_envelope(**_kwargs(route="invalid_route"))


@pytest.mark.unit
def test_invalid_triggered_by_rejected() -> None:
    with pytest.raises(NakedOutputError):
        build_envelope(**_kwargs(triggered_by="cron"))  # not a valid enum value


# ── autonomous-route invariant ────────────────────────────────────────────


@pytest.mark.unit
def test_autonomous_route_requires_non_empty_derivation() -> None:
    """Per MD: AUTONOMOUS route cannot act on no proof."""
    with pytest.raises(NakedOutputError):
        build_envelope(**_kwargs(route="autonomous", derivation=[]))


@pytest.mark.unit
def test_autonomous_with_derivation_ok() -> None:
    env = build_envelope(**_kwargs(route="autonomous"))
    assert env.route == EnvelopeRoute.AUTONOMOUS
    assert len(env.derivation) == 1


# ── frozen invariant ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_envelope_is_frozen() -> None:
    from pydantic import ValidationError

    env = build_envelope(**_kwargs())
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        env.confidence = 0.5  # type: ignore[misc]


# ── extras rejected (no smuggling) ────────────────────────────────────────


@pytest.mark.unit
def test_extras_rejected_at_pydantic_level() -> None:
    """extra='forbid' blocks unknown fields — no smuggled metadata."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Envelope.model_validate(
            {
                "recommendation": {},
                "confidence": "high",
                "derivation": [],
                "uncertainty": [],
                "route": "notify",
                "triggered_by": "query",
                "as_of": {"graph_version": 1, "timestamp": _now().isoformat()},
                "decision_id": "d",
                "org_id": "o",
                "smuggled_field": "should be rejected",
            }
        )

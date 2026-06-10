"""Tests for core.neural.confidence — external confidence + constraint_pass hard gate."""

from __future__ import annotations

import pytest

from core.neural.confidence import ConfidenceScorer, consistency_from_samples


@pytest.mark.unit
def test_constraint_pass_false_zeroes_confidence() -> None:
    """HARD GATE: constraint_pass=False -> overall=0 regardless of other components."""
    scorer = ConfidenceScorer()
    result = scorer.score(
        constraint_pass=False,
        grounding_score=1.0,
        consistency_score=1.0,
        symbolic_support=True,
    )
    assert result.overall == 0.0
    assert result.constraint_pass is False


@pytest.mark.unit
def test_full_signal_yields_max_confidence() -> None:
    """All components at 1.0 + constraint_pass -> overall ~= 1.0."""
    scorer = ConfidenceScorer()
    result = scorer.score(
        constraint_pass=True,
        grounding_score=1.0,
        consistency_score=1.0,
        symbolic_support=True,
    )
    assert result.overall == pytest.approx(1.0, abs=0.01)
    assert result.constraint_pass is True


@pytest.mark.unit
def test_partial_grounding_lowers_score() -> None:
    scorer = ConfidenceScorer()
    full = scorer.score(
        constraint_pass=True, grounding_score=1.0, consistency_score=1.0, symbolic_support=True
    )
    partial = scorer.score(
        constraint_pass=True, grounding_score=0.5, consistency_score=1.0, symbolic_support=True
    )
    assert partial.overall < full.overall


@pytest.mark.unit
def test_no_symbolic_support_lowers_score() -> None:
    scorer = ConfidenceScorer()
    with_sym = scorer.score(
        constraint_pass=True, grounding_score=1.0, consistency_score=1.0, symbolic_support=True
    )
    no_sym = scorer.score(
        constraint_pass=True, grounding_score=1.0, consistency_score=1.0, symbolic_support=False
    )
    assert no_sym.overall < with_sym.overall


@pytest.mark.unit
def test_invalid_score_range_rejected() -> None:
    scorer = ConfidenceScorer()
    with pytest.raises(ValueError):
        scorer.score(
            constraint_pass=True,
            grounding_score=1.5,
            consistency_score=1.0,
            symbolic_support=True,
        )


@pytest.mark.unit
def test_weights_must_sum_to_unit() -> None:
    with pytest.raises(ValueError):
        ConfidenceScorer({"grounding": 0.5, "consistency": 0.5, "symbolic": 0.5})


# ── consistency helper ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_consistency_all_agree() -> None:
    assert consistency_from_samples(["yes", "yes", "yes"]) == 1.0


@pytest.mark.unit
def test_consistency_split() -> None:
    assert consistency_from_samples(["yes", "yes", "no"]) == pytest.approx(2 / 3)


@pytest.mark.unit
def test_consistency_normalizes_whitespace_and_case() -> None:
    assert consistency_from_samples([" Yes ", "yes", "YES"]) == 1.0


@pytest.mark.unit
def test_consistency_empty_zero() -> None:
    assert consistency_from_samples([]) == 0.0

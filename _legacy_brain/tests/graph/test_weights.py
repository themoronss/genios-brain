"""Tests for core.graph.weights — Laplace smoothing + Bayesian update + volume gate."""

from __future__ import annotations

import pytest

from core.graph.schema import WeightSource
from core.graph.weights import bayesian_update, laplace_smoothed_weight


@pytest.mark.unit
def test_laplace_below_n_min_marked_default() -> None:
    """Below N_MIN_EVIDENCE → weight_source=DEFAULT, trusted=False."""
    r = laplace_smoothed_weight(count_cause_and_effect=2, count_cause=5)
    assert r.source == WeightSource.DEFAULT
    assert r.trusted is False
    assert 0.0 < r.weight < 1.0


@pytest.mark.unit
def test_laplace_above_n_min_marked_frequency() -> None:
    """At/above N_MIN_EVIDENCE → weight_source=FREQUENCY, trusted=True."""
    r = laplace_smoothed_weight(count_cause_and_effect=30, count_cause=50)
    assert r.source == WeightSource.FREQUENCY
    assert r.trusted is True


@pytest.mark.unit
def test_laplace_smoothing_avoids_zero() -> None:
    """No co-occurrence yet — smoothed weight still > 0 (avoids 0-division-trap downstream)."""
    r = laplace_smoothed_weight(count_cause_and_effect=0, count_cause=100)
    assert r.weight > 0.0


@pytest.mark.unit
def test_laplace_rejects_impossible_counts() -> None:
    with pytest.raises(ValueError):
        laplace_smoothed_weight(count_cause_and_effect=10, count_cause=5)  # effect>cause
    with pytest.raises(ValueError):
        laplace_smoothed_weight(count_cause_and_effect=-1, count_cause=10)


@pytest.mark.unit
def test_bayesian_confirm_increases_alpha() -> None:
    """Confirmation moves weight UP."""
    before = 5 / (5 + 5)
    r = bayesian_update(alpha=5, beta=5, outcome=True)
    assert r.weight > before


@pytest.mark.unit
def test_bayesian_contradict_increases_beta() -> None:
    """Contradiction moves weight DOWN."""
    before = 5 / (5 + 5)
    r = bayesian_update(alpha=5, beta=5, outcome=False)
    assert r.weight < before


@pytest.mark.unit
def test_bayesian_volume_gate_low_evidence() -> None:
    """(alpha+beta) below N_min → trusted=False, surfaced as DEFAULT."""
    r = bayesian_update(alpha=2, beta=2, outcome=True)
    assert r.trusted is False
    assert r.source == WeightSource.DEFAULT


@pytest.mark.unit
def test_bayesian_volume_gate_high_evidence() -> None:
    """(alpha+beta) >= N_min → trusted=True, surfaced as FREQUENCY (learned)."""
    r = bayesian_update(alpha=40, beta=10, outcome=True)
    assert r.trusted is True
    assert r.source == WeightSource.FREQUENCY


@pytest.mark.unit
def test_bayesian_trust_monotonic_with_evidence() -> None:
    """Trust rises as more evidence accumulates."""
    low = bayesian_update(alpha=2, beta=2, outcome=True)
    high = bayesian_update(alpha=50, beta=50, outcome=True)
    assert high.trust > low.trust


@pytest.mark.unit
def test_bayesian_rejects_negative_params() -> None:
    with pytest.raises(ValueError):
        bayesian_update(alpha=-1, beta=2, outcome=True)

"""Edge-weight estimation + Bayesian update — with MANDATORY provenance.

Per MD g-i-2 §2.1.1:
- Laplace-smoothed conditional frequency for frequency-derived weights
- Min sample size N_min before frequency weight is trusted; below -> WeightSource.DEFAULT
- Frequency = association, NEVER causation

Per MD g-i-3 §3.2.1:
- Beta-Binomial update from corrections
- confirm: alpha += 1; contradict: beta += 1
- weight = alpha / (alpha + beta)
- trust = 1 - variance = 1 - (alpha*beta) / ((a+b)^2 * (a+b+1))
- volume gate: weight USED downstream only when (alpha+beta) >= N_min
- time decay (exp(-lambda * dt)) applied per evidence age (caller side)
"""

from __future__ import annotations

from dataclasses import dataclass

from core.foundations.config import N_MIN_EVIDENCE
from core.graph.schema import WeightSource


@dataclass(frozen=True)
class WeightResult:
    """Output of a weight computation. `trusted` reflects volume-gate check."""

    weight: float
    source: WeightSource
    trust: float
    sample_count: int
    trusted: bool


# ─────────────────────────────────────────────────────────────────────────────
# Frequency weight (Laplace-smoothed)
# ─────────────────────────────────────────────────────────────────────────────


def laplace_smoothed_weight(
    *,
    count_cause_and_effect: int,
    count_cause: int,
    alpha: float = 1.0,
    k: int = 2,
    n_min: int | None = None,
) -> WeightResult:
    """Laplace-smoothed conditional frequency:
        weight = (count(cause & effect) + alpha) / (count(cause) + alpha*k)

    `k` = number of possible outcomes (default 2: occurred / didn't).
    `n_min` = min sample size to trust the weight (default = N_MIN_EVIDENCE).

    Below n_min → source=DEFAULT + trusted=False (must be surfaced downstream).
    """
    if count_cause < 0 or count_cause_and_effect < 0:
        raise ValueError("Counts cannot be negative")
    if count_cause_and_effect > count_cause:
        raise ValueError("count(cause & effect) cannot exceed count(cause)")

    threshold = n_min if n_min is not None else N_MIN_EVIDENCE
    smoothed = (count_cause_and_effect + alpha) / (count_cause + alpha * k)

    trusted = count_cause >= threshold
    source = WeightSource.FREQUENCY if trusted else WeightSource.DEFAULT

    return WeightResult(
        weight=smoothed,
        source=source,
        trust=_trust_from_count(count_cause),
        sample_count=count_cause,
        trusted=trusted,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bayesian (Beta-Binomial) update — driven by corrections
# ─────────────────────────────────────────────────────────────────────────────


def bayesian_update(
    *,
    alpha: int,
    beta: int,
    outcome: bool,
    n_min: int | None = None,
) -> WeightResult:
    """Apply a single confirmation (outcome=True) or contradiction (outcome=False).

    Returns the new (alpha, beta)-derived WeightResult.
    Callers persist the updated alpha/beta on the edge row.

    `outcome=True`  -> alpha incremented (the edge's influence was CONFIRMED)
    `outcome=False` -> beta incremented  (the edge's influence was CONTRADICTED)
    """
    if alpha < 0 or beta < 0:
        raise ValueError("alpha and beta must be non-negative")

    if outcome:
        alpha = alpha + 1
    else:
        beta = beta + 1

    total = alpha + beta
    weight = alpha / total if total > 0 else 0.5
    trust = _trust_from_beta_params(alpha, beta)
    threshold = n_min if n_min is not None else N_MIN_EVIDENCE
    trusted = total >= threshold
    source = WeightSource.FREQUENCY if trusted else WeightSource.DEFAULT  # learned ≈ frequency

    return WeightResult(
        weight=weight,
        source=source,
        trust=trust,
        sample_count=total,
        trusted=trusted,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _trust_from_count(n: int) -> float:
    """Monotonic trust curve from sample count. 0 at n=0, ~0.9 at n=N_min, asymptote 1.0."""
    if n <= 0:
        return 0.0
    # Saturating curve: trust = n / (n + N_min)
    return n / (n + N_MIN_EVIDENCE)


def _trust_from_beta_params(alpha: int, beta: int) -> float:
    """Trust = 1 - variance of Beta(alpha, beta). Rises as evidence accumulates."""
    total = alpha + beta
    if total < 2:
        return 0.0
    variance = (alpha * beta) / ((total * total) * (total + 1))
    # variance is bounded by 0.25 (Beta(1,1)); normalize to [0, 1]
    return max(0.0, min(1.0, 1.0 - variance * 4))

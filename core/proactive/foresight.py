"""Foresight — what could happen + PREMORTEM (failure-mode what-if).

Per MD g-i-4 §1.1.2:
    MODE A (base-rate grounded): laplace_smoothed_rate over historical comparables.
                                  REQUIRE: report n (sample size). If n < N_min -> Mode B.
    MODE B (qualitative): high | medium | low, justified by the derivation chain.
    FORBIDDEN: numeric probability with no empirical base (false precision).

Premortem mode (per MD adoption from techniques-decisions):
    failure-mode what-if — "what would have to be true for this goal to FAIL?"
    Reuses core.reasoning.what_if.premortem (already builds failure paths +
    load-bearing assumptions). Output carries the "bounded by asserted model"
    disclaimer at the dataclass level (cannot be stripped downstream).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from core.foundations.config import FORESIGHT_N_MIN
from core.foundations.telemetry import get_logger
from core.reasoning.rule_loader import RuleSet
from core.reasoning.what_if import PremortemResult, premortem

log = get_logger(__name__)


class ForesightMode(StrEnum):
    BASE_RATE = "base_rate"
    QUALITATIVE = "qualitative"


@dataclass(frozen=True)
class ForesightResult:
    """Foresight output. Always carries mode + (for base-rate) sample size."""

    mode: ForesightMode
    value: float | str
    basis: str
    sample_size: int | None
    disclaimer: str
    premortem: PremortemResult | None = None


_DISCLAIMER_QUAL = (
    "Likelihood is qualitative (high/medium/low) — the asserted model has insufficient "
    "comparable cases for a base-rate. Treat as exploratory."
)
_DISCLAIMER_BASE_RATE = (
    "Likelihood is base-rate from {n} comparable historical cases. Bounded by the asserted model."
)


def estimate_likelihood(
    *,
    historical_outcomes: list[bool] | None = None,
    qualitative_default: str = "medium",
    n_min: int = FORESIGHT_N_MIN,
) -> ForesightResult:
    """Mode A if n >= n_min historical comparables; else Mode B qualitative.

    Args:
        historical_outcomes: list of bool (True = goal happened in this past case)
        qualitative_default: when falling back to Mode B
        n_min: minimum samples needed for base-rate (default from config)
    """
    n = len(historical_outcomes) if historical_outcomes is not None else 0

    if n >= n_min and historical_outcomes is not None:
        # Laplace smoothing — avoid 0/1 extremes on small n
        positives = sum(1 for o in historical_outcomes if o)
        rate = (positives + 1) / (n + 2)
        return ForesightResult(
            mode=ForesightMode.BASE_RATE,
            value=round(rate, 3),
            basis=f"{positives}/{n} comparable cases positive (Laplace-smoothed)",
            sample_size=n,
            disclaimer=_DISCLAIMER_BASE_RATE.format(n=n),
        )

    # Mode B — strictly qualitative
    if qualitative_default not in {"high", "medium", "low"}:
        qualitative_default = "medium"
    return ForesightResult(
        mode=ForesightMode.QUALITATIVE,
        value=qualitative_default,
        basis=f"only {n} historical comparables (need >= {n_min}); falling back to qualitative",
        sample_size=n if n > 0 else None,
        disclaimer=_DISCLAIMER_QUAL,
    )


def compute_premortem(
    *,
    ruleset: RuleSet,
    facts: dict[str, Any],
    goal: str,
    candidate_interventions: list[dict[str, Any]],
) -> PremortemResult:
    """Run failure-mode what-if. Returns the interventions that BREAK the goal.

    Thin wrapper over core.reasoning.what_if.premortem — kept here as the
    proactive-layer entry point so callers don't have to reach into reasoning.
    """
    return premortem(
        ruleset=ruleset,
        facts=facts,
        goal=goal,
        candidate_interventions=candidate_interventions,
    )

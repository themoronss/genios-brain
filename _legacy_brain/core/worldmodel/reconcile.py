"""Conflict reconciliation — trust x recency_decay (per MD g-i-3 §3.1.1).

When two sources disagree on an attribute (CRM says $50K, email says $80K):
- resolved_value = argmax_candidate( source_trust * recency_decay )
- If top two candidates within epsilon -> FLAG for human (do NOT silently pick)
- Losing value preserved in history with provenance (caller persists)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

# Default trust per source_type (override per-org via config later)
DEFAULT_SOURCE_TRUST: dict[str, float] = {
    "gmail": 0.7,
    "notion": 0.8,
    "drive": 0.7,
    "calendar": 0.85,
    "crm": 0.9,
    "custom": 0.6,
}

# 90-day half-life — recent evidence weighs more
DEFAULT_HALF_LIFE_DAYS = 90.0

# Epsilon: if top two scores differ by less than this, flag for human
DEFAULT_EPSILON = 0.05


@dataclass(frozen=True)
class Candidate:
    """One source's vote for an attribute value."""

    value: object
    source_type: str
    asserted_at: datetime


@dataclass(frozen=True)
class Reconciliation:
    """Outcome of reconciling N competing values."""

    winning_value: object | None
    winning_source_type: str | None
    score: float
    runner_up_score: float
    flagged_for_human: bool
    losing_history: list[Candidate]


def reconcile(
    candidates: list[Candidate],
    *,
    now: datetime | None = None,
    trust_map: dict[str, float] | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    epsilon: float = DEFAULT_EPSILON,
) -> Reconciliation:
    """Pick a winner; flag if top two too close.

    Empty candidates -> flagged with no winner.
    """
    if not candidates:
        return Reconciliation(
            winning_value=None,
            winning_source_type=None,
            score=0.0,
            runner_up_score=0.0,
            flagged_for_human=True,
            losing_history=[],
        )

    now = now or datetime.now(UTC)
    tm = trust_map or DEFAULT_SOURCE_TRUST

    scored = [
        (c, _score(c, now=now, trust_map=tm, half_life_days=half_life_days)) for c in candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_cand, top_score = scored[0]
    runner_score = scored[1][1] if len(scored) > 1 else 0.0
    flagged = (top_score - runner_score) < epsilon and len(scored) > 1

    losers = [c for c, _s in scored[1:]] if not flagged else [c for c, _s in scored]

    return Reconciliation(
        winning_value=None if flagged else top_cand.value,
        winning_source_type=None if flagged else top_cand.source_type,
        score=top_score,
        runner_up_score=runner_score,
        flagged_for_human=flagged,
        losing_history=losers,
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _score(
    c: Candidate,
    *,
    now: datetime,
    trust_map: dict[str, float],
    half_life_days: float,
) -> float:
    """trust * recency_decay."""
    trust = trust_map.get(c.source_type, 0.5)
    # Exponential decay with given half-life
    age_days = (now - _to_utc(c.asserted_at)).total_seconds() / 86400.0
    if age_days < 0:
        age_days = 0.0
    decay: float = 0.5 ** (age_days / half_life_days)
    return float(trust * decay)


def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

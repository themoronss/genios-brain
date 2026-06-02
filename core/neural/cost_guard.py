"""Per-org LLM cost cap + circuit breaker.

Per MD g-i-2 acceptance: per-org LLM cost tracked; breach → circuit breaker stops gap-fill calls.
Per GENIOS_V2_PLAN.md Group 2: LLM_DAILY_BUDGET_USD defaults: default=$10, design_partner=$50.
Circuit breaker fires at 1.5x daily budget (hard halt).

Storage: Redis with daily-expiring keys. No new DB table needed for v1.
Key format: `genios:cost:{org_id}:{YYYY-MM-DD}` -> accumulated cost in cents (int).

Why cents (int) not float USD: Redis INCRBY is integer-only and atomic; floating-point
sum-then-set has race conditions across workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import redis

from core.foundations import audit
from core.foundations.config import (
    LLM_CIRCUIT_BREAKER_THRESHOLD,
    LLM_DAILY_BUDGET_USD,
    settings,
)
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


class BudgetExceededError(Exception):
    """Raised when an org is past their LLM budget (1.5x daily cap)."""


@dataclass(frozen=True)
class BudgetStatus:
    """Snapshot of an org's daily LLM spend."""

    org_id: str
    date: str  # YYYY-MM-DD
    spent_usd: float
    daily_budget_usd: float
    breaker_threshold_usd: float
    halted: bool


class CostGuard:
    """Tracks per-org daily LLM spend via Redis. Halts when over circuit-breaker threshold."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis: redis.Redis = redis.Redis.from_url(redis_url or settings.REDIS_URL)

    # ── budget lookup ──────────────────────────────────────────────────────

    def daily_budget_for(self, org_id: str) -> float:
        """Return the configured daily budget for an org. Currently uses the 'default' tier.

        Per-org tier override lands with `org_tunables` (g-i-8).
        """
        return LLM_DAILY_BUDGET_USD.get("default", 10.0)

    def status(self, org_id: str) -> BudgetStatus:
        """Read-only snapshot."""
        date = _today()
        raw = self._redis.get(_key(org_id, date))
        spent_cents = int(raw) if raw is not None else 0  # type: ignore[arg-type]
        budget = self.daily_budget_for(org_id)
        threshold = budget * LLM_CIRCUIT_BREAKER_THRESHOLD
        spent_usd = spent_cents / 100.0
        return BudgetStatus(
            org_id=org_id,
            date=date,
            spent_usd=spent_usd,
            daily_budget_usd=budget,
            breaker_threshold_usd=threshold,
            halted=spent_usd >= threshold,
        )

    # ── pre-call gate ──────────────────────────────────────────────────────

    def require_capacity(self, org_id: str) -> None:
        """Raise BudgetExceededError if the org is already past the breaker threshold.

        Called BEFORE the LLM call. Sub-budget but-over-threshold is allowed; only
        the absolute breaker (1.5x) halts.
        """
        s = self.status(org_id)
        if s.halted:
            log.warning(
                "llm_budget_halt",
                org_id=org_id,
                spent_usd=s.spent_usd,
                threshold_usd=s.breaker_threshold_usd,
            )
            audit.record(
                org_id=org_id,
                actor_type="system",
                actor_id="cost_guard",
                action="config_changed",
                target_type="budget",
                target_id=s.date,
                metadata={
                    "outcome": "halted",
                    "spent_usd": round(s.spent_usd, 4),
                    "threshold_usd": round(s.breaker_threshold_usd, 4),
                },
            )
            raise BudgetExceededError(
                f"LLM budget exceeded for org {org_id}: "
                f"${s.spent_usd:.2f} >= ${s.breaker_threshold_usd:.2f} threshold"
            )

    # ── post-call accounting ───────────────────────────────────────────────

    def charge(self, org_id: str, cost_usd: float) -> BudgetStatus:
        """Record cost after a successful LLM call. Atomic INCRBY on Redis.

        Returns the post-charge status. If the org just crossed daily-budget
        (warning) or threshold (halt), the relevant audit event fires.
        """
        if cost_usd <= 0:
            return self.status(org_id)

        date = _today()
        key = _key(org_id, date)
        cents = max(1, round(cost_usd * 100))
        pipe = self._redis.pipeline()
        pipe.incrby(key, cents)
        pipe.expire(key, 60 * 60 * 36)  # 36h TTL — covers tz drift
        new_cents = int(pipe.execute()[0])

        budget = self.daily_budget_for(org_id)
        threshold = budget * LLM_CIRCUIT_BREAKER_THRESHOLD
        spent_usd = new_cents / 100.0
        status = BudgetStatus(
            org_id=org_id,
            date=date,
            spent_usd=spent_usd,
            daily_budget_usd=budget,
            breaker_threshold_usd=threshold,
            halted=spent_usd >= threshold,
        )

        # Crossing thresholds (warn / halt) emits audit events
        prev_usd = (new_cents - cents) / 100.0
        if prev_usd < budget <= spent_usd:
            log.warning(
                "llm_budget_exceeded_warning",
                org_id=org_id,
                spent_usd=spent_usd,
                budget_usd=budget,
            )
        if prev_usd < threshold <= spent_usd:
            log.error(
                "llm_breaker_tripped",
                org_id=org_id,
                spent_usd=spent_usd,
                threshold_usd=threshold,
            )

        return status


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _key(org_id: str, date: str) -> str:
    return f"genios:cost:{org_id}:{date}"

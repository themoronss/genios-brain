"""Layer 4 · Part 1 — execution telemetry.

Every unit declares a `latency_budget_ms`.  Until now nothing ever looked at it at runtime, so a
unit could quietly become ten times slower and the only symptom would be a slow product.  This
module observes what actually happened.

**Telemetry is never a decision input.**  A stopwatch reading differs between a laptop and a
loaded production box, so letting elapsed time reach the decision would make the same situation
resolve differently depending on the machine — and a decision that cannot be reproduced cannot be
audited, which is the one thing Layer 4 must never give up.  So timings live here, outside the
semantic hash, and the orchestrator never branches on them.

That is also why there is no wall-clock timeout that kills a running unit.  Cancelling work mid-run
would make the result depend on machine speed, turning a deterministic decision into a race.  The
budget is enforced *statically* instead — the planner refuses a capability whose declared budgets
exceed its declared ceiling — and enforced *socially* here, by making an overrun loud and
attributable.  A breach is a bug to fix in the unit, not a decision to alter at runtime.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StepTiming:
    """What one unit declared it would cost, and what it actually cost."""

    reasoner_id: str
    reasoner_version: str
    stage: int
    elapsed_us: int
    budget_ms: int

    @property
    def elapsed_ms(self) -> int:
        # Microsecond capture, millisecond reporting: most units finish well inside 1ms, and
        # rounding those to zero would hide the difference between fast and not-run-at-all.
        return self.elapsed_us // 1_000

    @property
    def over_budget(self) -> bool:
        return self.elapsed_us > self.budget_ms * 1_000

    @property
    def budget_used_bp(self) -> int:
        """Share of the declared budget consumed, in basis points."""
        if self.budget_ms <= 0:
            return 10_000
        return min(100_000, (self.elapsed_us * 10_000) // (self.budget_ms * 1_000))


@dataclass(frozen=True, slots=True)
class ExecutionTelemetry:
    """Observed cost of one run.  Diagnostic only — excluded from every semantic hash."""

    timings: tuple[StepTiming, ...] = ()

    @property
    def elapsed_us(self) -> int:
        return sum(item.elapsed_us for item in self.timings)

    @property
    def elapsed_ms(self) -> int:
        return self.elapsed_us // 1_000

    @property
    def breaches(self) -> tuple[StepTiming, ...]:
        return tuple(item for item in self.timings if item.over_budget)

    @property
    def slowest(self) -> StepTiming | None:
        return max(self.timings, key=lambda item: item.elapsed_us, default=None)

    def describe(self) -> str:
        if not self.timings:
            return "no units executed"
        lines = [f"{self.elapsed_ms}ms across {len(self.timings)} units"]
        for item in sorted(self.timings, key=lambda entry: -entry.elapsed_us):
            flag = "  OVER BUDGET" if item.over_budget else ""
            lines.append(f"  {item.reasoner_id}@{item.reasoner_version}: "
                         f"{item.elapsed_ms}ms of {item.budget_ms}ms declared"
                         f" ({item.budget_used_bp}bp){flag}")
        return "\n".join(lines)


class TelemetryRecorder:
    """Collects step timings during one execution.

    Uses a monotonic clock so a system clock adjustment mid-run cannot produce a negative or wildly
    inflated duration — the measurement must stay trustworthy precisely when the machine is not.
    """

    __slots__ = ("_timings",)

    def __init__(self) -> None:
        self._timings: list[StepTiming] = []

    def record(self, *, reasoner_id: str, reasoner_version: str, stage: int,
               started_ns: int, ended_ns: int, budget_ms: int) -> None:
        self._timings.append(StepTiming(
            reasoner_id=reasoner_id,
            reasoner_version=reasoner_version,
            stage=stage,
            elapsed_us=max(0, (ended_ns - started_ns) // 1_000),
            budget_ms=budget_ms,
        ))

    @staticmethod
    def now_ns() -> int:
        return time.monotonic_ns()

    def finish(self) -> ExecutionTelemetry:
        return ExecutionTelemetry(timings=tuple(self._timings))


def log_budget_breaches(telemetry: ExecutionTelemetry, *, capability_id: str,
                        capability_version: str) -> None:
    """Make an overrun visible and attributable, without changing the decision it came from."""
    for breach in telemetry.breaches:
        logger.warning(
            "layer4 reasoner over declared budget: %s@%s in %s@%s took %dms of %dms",
            breach.reasoner_id, breach.reasoner_version, capability_id, capability_version,
            breach.elapsed_ms, breach.budget_ms)


def aggregate(runs: Iterable[ExecutionTelemetry]) -> dict[str, int]:
    """Roll several runs into per-unit worst observed cost, for capability tuning."""
    worst: dict[str, int] = {}
    for run in runs:
        for item in run.timings:
            worst[item.reasoner_id] = max(worst.get(item.reasoner_id, 0), item.elapsed_us)
    return worst


def slowest_first(timings: Sequence[StepTiming]) -> tuple[StepTiming, ...]:
    return tuple(sorted(timings, key=lambda item: (-item.elapsed_us, item.reasoner_id)))


__all__ = ["ExecutionTelemetry", "StepTiming", "TelemetryRecorder", "aggregate",
           "log_budget_breaches", "slowest_first"]

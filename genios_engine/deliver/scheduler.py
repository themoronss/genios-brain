"""Layer 5.2 · Phase 2 — the Priority Scheduler (section 5.6 / responsibility 7).

Two pure jobs: order due deliveries by business priority, and age waiting rows so low-priority
work cannot starve forever behind a steady stream of high-priority work. No model, no clock read —
the caller passes ``now`` so the ordering is replayable.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from genios_engine.contracts.delivery import DeliveryPriority, _PRIORITY_RANK

#: A waiting row climbs one priority class per this many hours, so nothing waits indefinitely.
STARVATION_STEP_HOURS = 4


def effective_rank(priority: DeliveryPriority, *, queued_at: datetime, now: datetime) -> int:
    """Priority rank after anti-starvation aging: +1 class per ``STARVATION_STEP_HOURS`` waited.

    Capped at CRITICAL. A background row that has waited a full day is not background any more;
    left un-aged it would sit behind every medium alert until the queue happened to empty.
    """
    base = _PRIORITY_RANK[priority.value]
    waited_hours = max(0.0, (now - queued_at).total_seconds() / 3600.0)
    bumped = base + int(waited_hours // STARVATION_STEP_HOURS)
    return min(bumped, _PRIORITY_RANK[DeliveryPriority.CRITICAL.value])


def rank_sql(priority_col: str, queued_col: str, now_param: str) -> str:
    """`effective_rank` as a SQL expression, generated from the SAME `_PRIORITY_RANK` map.

    The v2 claimer ordered by `priority` directly — a `text` column, so Postgres sorted it
    alphabetically: background < critical < high < low < medium. A `critical` delivery was claimed
    after `background` work, and every correct rank already existed in this module with nothing
    importing it outside tests.

    Generated rather than hand-written so the two orderings cannot drift: adding a priority class
    to the enum changes both at once or neither.
    """
    cases = " ".join(f"when {priority_col} = '{value}' then {rank}"
                     for value, rank in _PRIORITY_RANK.items())
    top = _PRIORITY_RANK[DeliveryPriority.CRITICAL.value]
    return (f"least((case {cases} else 0 end) + "
            f"floor(extract(epoch from ({now_param} - {queued_col})) / 3600 "
            f"/ {STARVATION_STEP_HOURS})::int, {top})")


def schedule_order(rows: Sequence[dict], *, now: datetime) -> list[dict]:
    """Order due rows: highest effective (aged) priority first, then oldest first.

    Each row needs ``priority`` (a ``DeliveryPriority`` or its value) and ``queued_at``. Ties break
    on ``queued_at`` ascending so within a class the queue is fair (FIFO), never arbitrary.
    """
    def key(row: dict) -> tuple[int, float]:
        pri = row["priority"]
        pri = pri if isinstance(pri, DeliveryPriority) else DeliveryPriority(pri)
        rank = effective_rank(pri, queued_at=row["queued_at"], now=now)
        return (-rank, row["queued_at"].timestamp())

    return sorted(rows, key=key)


__all__ = ["STARVATION_STEP_HOURS", "effective_rank", "rank_sql", "schedule_order"]

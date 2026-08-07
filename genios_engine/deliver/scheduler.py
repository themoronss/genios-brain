"""Deterministic Atlas priority scheduling for Layer 5.2.

Layer 5 supplies a 0..10,000 business priority. Delivery maps that immutable number onto the
five Atlas scheduling classes. The mapping changes neither the recommendation nor its business
priority; it only determines which already-due delivery claims a worker first.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum


class PriorityClass(str, Enum):
    BACKGROUND = "background"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_ORDER: tuple[PriorityClass, ...] = (
    PriorityClass.BACKGROUND,
    PriorityClass.LOW,
    PriorityClass.MEDIUM,
    PriorityClass.HIGH,
    PriorityClass.CRITICAL,
)


def priority_class(priority_bp: int) -> PriorityClass:
    """Map Layer 5's declared priority onto Atlas' five delivery queues."""
    if isinstance(priority_bp, bool) or not isinstance(priority_bp, int):
        raise TypeError("priority_bp must be an integer")
    if not 0 <= priority_bp <= 10_000:
        raise ValueError("priority_bp must be between 0 and 10000")
    if priority_bp >= 8_500:
        return PriorityClass.CRITICAL
    if priority_bp >= 7_000:
        return PriorityClass.HIGH
    if priority_bp >= 4_000:
        return PriorityClass.MEDIUM
    if priority_bp >= 2_000:
        return PriorityClass.LOW
    return PriorityClass.BACKGROUND


def priority_rank(value: PriorityClass | str) -> int:
    item = value if isinstance(value, PriorityClass) else PriorityClass(value)
    return PRIORITY_ORDER.index(item) + 1


def effective_rank(value: PriorityClass | str, *, created_at: datetime, now: datetime,
                   aging_minutes: int = 240) -> int:
    """Age a waiting item one class per interval, capped at critical.

    This prevents a continuous critical stream from starving low/background work forever while
    retaining strict class ordering for newly queued work.
    """
    if created_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("created_at and now must be timezone-aware")
    if aging_minutes <= 0:
        raise ValueError("aging_minutes must be positive")
    waited = max(0, int((now - created_at).total_seconds()) // 60)
    return min(5, priority_rank(value) + waited // aging_minutes)


__all__ = ["PRIORITY_ORDER", "PriorityClass", "effective_rank", "priority_class",
           "priority_rank"]

"""Deterministic Layer 5.2 delivery analytics over the one durable ledger."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text


ANALYTICS_VERSION = "delivery-analytics.v1"
_TERMINAL = frozenset({"delivered", "suppressed", "cancelled", "failed_terminal"})
_TRANSPORT_TERMINAL = frozenset({"delivered", "failed_terminal"})


def _bp(numerator: int, denominator: int) -> int:
    return 0 if denominator <= 0 else (numerator * 10_000 + denominator // 2) // denominator


def summarize(rows: Iterable[Mapping[str, Any]], *, since: datetime,
              until: datetime) -> dict[str, Any]:
    """Reduce delivery rows into counted, reproducible metrics.

    No averages are produced from missing clocks, and queued rows are excluded from terminal
    success rates rather than being guessed into failures.
    """
    records = [dict(row) for row in rows]
    statuses = Counter(str(row.get("status") or "unknown") for row in records)
    by_channel: dict[str, Counter] = defaultdict(Counter)
    latencies: list[int] = []
    attempts = 0
    deferrals = 0
    burst_holds = 0
    for row in records:
        status = str(row.get("status") or "unknown")
        channel = str(row.get("channel") or "unknown")
        by_channel[channel][status] += 1
        attempts += max(0, int(row.get("attempts") or 0))
        deferrals += max(0, int(row.get("defer_count") or 0))
        burst_holds += int(row.get("gate_reason") == "burst_limit")
        created, delivered = row.get("created_at"), row.get("delivered_at")
        if isinstance(created, datetime) and isinstance(delivered, datetime):
            latencies.append(max(0, int((delivered - created).total_seconds() * 1000)))

    terminal = sum(statuses[name] for name in _TERMINAL)
    transport_terminal = sum(statuses[name] for name in _TRANSPORT_TERMINAL)
    delivered = statuses["delivered"]
    failed = statuses["failed_terminal"]
    latencies.sort()
    p50 = latencies[(len(latencies) - 1) // 2] if latencies else None
    p95 = latencies[max(0, (len(latencies) * 95 + 99) // 100 - 1)] if latencies else None
    return {
        "schema_version": ANALYTICS_VERSION,
        "window": {"since": since, "until": until},
        "total": len(records),
        "status_counts": dict(sorted(statuses.items())),
        "delivered_bp": _bp(delivered, terminal),
        "transport_failure_bp": _bp(failed, transport_terminal),
        "transport_attempts": attempts,
        "deferrals": deferrals,
        "burst_holds": burst_holds,
        "latency_ms": {"p50": p50, "p95": p95},
        "channels": {name: dict(sorted(counts.items()))
                     for name, counts in sorted(by_channel.items())},
    }


def load_analytics(conn, org_id: str, *, days: int = 28,
                   now: datetime | None = None) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    window_days = max(1, min(int(days), 365))
    since = moment - timedelta(days=window_days)
    rows = conn.execute(text(
        "select channel, status, attempts, defer_count, gate_reason, created_at, delivered_at "
        "from delivery_outbox where org_id=:o and created_at>=:since and created_at<:until"),
        {"o": org_id, "since": since, "until": moment}).mappings().all()
    return summarize(rows, since=since, until=moment)


__all__ = ["ANALYTICS_VERSION", "load_analytics", "summarize"]

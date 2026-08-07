"""Deterministic Layer 5.2 delivery analytics over the one durable ledger."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text


ANALYTICS_VERSION = "delivery-analytics.v2"
_TERMINAL = frozenset({"delivered", "viewed", "ignored", "accepted", "executed",
                       "expired", "suppressed", "cancelled", "failed", "failed_terminal"})
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
    statuses = Counter(str(row.get("lifecycle_status") or row.get("status") or "unknown")
                       for row in records)
    transport_statuses = Counter(str(row.get("status") or "unknown") for row in records)
    by_channel: dict[str, Counter] = defaultdict(Counter)
    latencies: list[int] = []
    attempts = 0
    deferrals = 0
    burst_holds = 0
    response_times: list[int] = []
    execution_times: list[int] = []
    recipients: dict[str, Counter] = defaultdict(Counter)
    for row in records:
        transport_status = str(row.get("status") or "unknown")
        status = str(row.get("lifecycle_status") or transport_status)
        channel = str(row.get("channel") or "unknown")
        by_channel[channel][status] += 1
        recipient = str(row.get("recipient") or "*")
        if isinstance(row.get("delivered_at"), datetime):
            recipients[recipient]["impressions"] += 1
        if isinstance(row.get("ignored_at"), datetime):
            recipients[recipient]["ignored"] += 1
        attempts += max(0, int(row.get("attempts") or 0))
        deferrals += max(0, int(row.get("defer_count") or 0))
        burst_holds += int(row.get("gate_reason") == "burst_limit")
        created, delivered = row.get("created_at"), row.get("delivered_at")
        if isinstance(created, datetime) and isinstance(delivered, datetime):
            latencies.append(max(0, int((delivered - created).total_seconds() * 1000)))
        engagement_clocks = [row.get(name) for name in
                             ("viewed_at", "accepted_at", "ignored_at", "executed_at")
                             if isinstance(row.get(name), datetime)]
        engagement = min(engagement_clocks) if engagement_clocks else None
        if isinstance(delivered, datetime) and isinstance(engagement, datetime):
            response_times.append(max(0, int((engagement - delivered).total_seconds() * 1000)))
        executed_at = row.get("executed_at")
        if isinstance(delivered, datetime) and isinstance(executed_at, datetime):
            execution_times.append(max(0, int((executed_at - delivered).total_seconds() * 1000)))

    terminal = sum(statuses[name] for name in _TERMINAL)
    transport_terminal = sum(transport_statuses[name] for name in _TRANSPORT_TERMINAL)
    delivered = sum(isinstance(row.get("delivered_at"), datetime) for row in records)
    failed = transport_statuses["failed_terminal"]
    latencies.sort()
    p50 = latencies[(len(latencies) - 1) // 2] if latencies else None
    p95 = latencies[max(0, (len(latencies) * 95 + 99) // 100 - 1)] if latencies else None
    response_times.sort()
    execution_times.sort()

    def percentile(values: list[int], percentage: int) -> int | None:
        if not values:
            return None
        return values[max(0, (len(values) * percentage + 99) // 100 - 1)]

    impression_count = delivered
    engaged_count = sum(any(isinstance(row.get(name), datetime) for name in
                            ("viewed_at", "ignored_at", "accepted_at", "executed_at"))
                        for row in records)
    ignored_count = sum(isinstance(row.get("ignored_at"), datetime) for row in records)
    accepted_count = sum(isinstance(row.get("accepted_at"), datetime)
                         or isinstance(row.get("executed_at"), datetime) for row in records)
    executed_count = sum(isinstance(row.get("executed_at"), datetime) for row in records)
    recipient_fatigue = {
        recipient: {
            "deliveries": counts["impressions"],
            "ignored": counts["ignored"],
            "ignore_bp": _bp(counts["ignored"], counts["impressions"]),
        }
        for recipient, counts in sorted(recipients.items())
    }
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
        "engagement": {
            "view_or_action_bp": _bp(engaged_count, impression_count),
            "ignore_bp": _bp(ignored_count, impression_count),
            "accept_bp": _bp(accepted_count, impression_count),
            "execute_bp": _bp(executed_count, impression_count),
            "response_time_ms": {"p50": percentile(response_times, 50),
                                 "p95": percentile(response_times, 95)},
            "execution_time_ms": {"p50": percentile(execution_times, 50),
                                  "p95": percentile(execution_times, 95)},
        },
        "fatigue": {"by_recipient": recipient_fatigue},
        "channels": {name: dict(sorted(counts.items()))
                     for name, counts in sorted(by_channel.items())},
    }


def load_analytics(conn, org_id: str, *, days: int = 28,
                   now: datetime | None = None) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    window_days = max(1, min(int(days), 365))
    since = moment - timedelta(days=window_days)
    rows = conn.execute(text(
        "select channel, status, lifecycle_status, recipient, attempts, defer_count, "
        "gate_reason, created_at, delivered_at, viewed_at, ignored_at, accepted_at, "
        "executed_at, expired_at "
        "from delivery_outbox where org_id=:o and created_at>=:since and created_at<:until"),
        {"o": org_id, "since": since, "until": moment}).mappings().all()
    return summarize(rows, since=since, until=moment)


__all__ = ["ANALYTICS_VERSION", "load_analytics", "summarize"]

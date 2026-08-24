"""Per-source metrics. Counts and refs ONLY — never content (g-i-8 rule).

What we measure (per g-i-1 observability requirement):
- items_pulled (per source, per org)
- scope_drops (per source, per scope grant)
- webhook events (accepted | rejected)
- batch runs (success | failure)
- sync lag (now - last_sync_at)

Implementation: structured log events tagged with measurable keys; an aggregator
in g-i-8 (`telemetry.py`) rolls these into `intervention_metrics` / dashboards.
For Phase 1, we emit the structured events; the rollup lands with g-i-8 DB tables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from core.foundations.telemetry import get_logger

log = get_logger(__name__)


BatchOutcome = Literal["success", "partial", "failure"]


def record_items_pulled(*, org_id: str, connection_id: str, source_type: str, count: int) -> None:
    log.info(
        "metric_items_pulled",
        org_id=org_id,
        connection_id=connection_id,
        source_type=source_type,
        count=count,
    )


def record_scope_drops(*, org_id: str, connection_id: str, count: int) -> None:
    if count == 0:
        return
    log.info(
        "metric_scope_drops",
        org_id=org_id,
        connection_id=connection_id,
        count=count,
    )


def record_webhook_event(
    *, org_id: str, connection_id: str, outcome: Literal["accepted", "rejected"]
) -> None:
    log.info(
        "metric_webhook_event",
        org_id=org_id,
        connection_id=connection_id,
        outcome=outcome,
    )


def record_batch_run(
    *,
    org_id: str,
    connection_id: str,
    source_type: str,
    outcome: BatchOutcome,
    duration_ms: int,
    items_emitted: int,
    scope_drops: int,
) -> None:
    log.info(
        "metric_batch_run",
        org_id=org_id,
        connection_id=connection_id,
        source_type=source_type,
        outcome=outcome,
        duration_ms=duration_ms,
        items_emitted=items_emitted,
        scope_drops=scope_drops,
    )


def record_sync_lag(*, org_id: str, connection_id: str, last_sync_at: datetime) -> None:
    lag_seconds = int((datetime.now(UTC) - last_sync_at).total_seconds())
    log.info(
        "metric_sync_lag",
        org_id=org_id,
        connection_id=connection_id,
        lag_seconds=lag_seconds,
    )

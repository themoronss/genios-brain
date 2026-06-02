"""Customer-facing health status for each connection.

GREEN / YELLOW / RED with last_sync_at, items_pulled count, scope_drops count.
Used by the dashboard health page (g-i-7 minimal dashboard).

Thresholds (move to config.py when first customer disagrees):
- GREEN  : last_sync_at within 2x cron interval, no recent errors
- YELLOW : last_sync_at within 6x cron interval OR recent recoverable error
- RED    : last_sync_at older than 6x cron interval OR persistent error / revoked
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.foundations.config import CRON_INTERVAL_HOURS
from core.memory.store import Connection, CursorRow
from core.memory.types import HealthStatus, HealthStatusLevel


def status_for(
    session: Session,
    *,
    connection_id: str,
) -> HealthStatus:
    """Compute current health for a single connection."""
    conn = session.get(Connection, connection_id)
    if conn is None:
        raise KeyError(f"connection {connection_id} not found")

    if conn.status in {"error", "revoked"}:
        return HealthStatus(
            level=HealthStatusLevel.RED,
            last_sync_at=None,
            items_pulled_count=0,
            scope_drops_count=0,
            last_error=conn.last_error,
        )

    cursor_row = session.get(CursorRow, connection_id)
    last_sync = cursor_row.last_sync_at if cursor_row else None
    items_pulled = cursor_row.items_pulled_count if cursor_row else 0

    drops = sum(g.scope_drops_count for g in conn.scope_grants)
    interval_hours = CRON_INTERVAL_HOURS.get(conn.source_type, CRON_INTERVAL_HOURS["default"])

    level = _level_for(last_sync, interval_hours, conn.last_error)

    return HealthStatus(
        level=level,
        last_sync_at=last_sync,
        items_pulled_count=items_pulled,
        scope_drops_count=drops,
        last_error=conn.last_error,
    )


def _level_for(
    last_sync_at: datetime | None,
    interval_hours: int,
    last_error: str | None,
) -> HealthStatusLevel:
    if last_sync_at is None:
        # Never synced — show yellow (pending) rather than red (broken)
        return HealthStatusLevel.YELLOW if last_error is None else HealthStatusLevel.RED

    age_hours = (datetime.now(UTC) - last_sync_at).total_seconds() / 3600.0
    green_limit = 2 * interval_hours
    yellow_limit = 6 * interval_hours

    if age_hours <= green_limit and not last_error:
        return HealthStatusLevel.GREEN
    if age_hours <= yellow_limit:
        return HealthStatusLevel.YELLOW
    return HealthStatusLevel.RED

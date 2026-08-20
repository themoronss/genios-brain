"""organization_reset — the pivot primitive.

A startup's ICP, positioning or product can change in a single afternoon. Without an explicit
invalidation event, the Adaptive brain keeps steering decisions on leases learned under the old
shape until their TTL happens to lapse, and open situations keep being scored against
now-obsolete state until the next daily L3 sweep. This module is that explicit event.

Deliberately narrow: it does NOT touch `learned_brain_entries` for brain='organization' or
brain='behavior'. Organization Brain has no declared-config table (ICP/products/policies) to
re-version yet, and `unit_behavior_evolution` (feedback/units.py) is presently an unwired stub
that always returns `[]` — there is no live Behavior Brain content to decay. Wiring those in is
follow-up work, not something to fake here.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from genios_engine.platform.ids import new_id


def apply_organization_reset(conn, *, org_id: str, reason: str, at: datetime,
                             actor: str | None = None) -> dict:
    """Expire every active Adaptive-brain lease predating ``at`` and log the reset event.

    Returns ``{"reset_id": ..., "adaptive_expired": <count>}``. Situation re-evaluation is the
    caller's job (it needs the L3 runner, which this module does not import to avoid a
    feedback → reason dependency); call :func:`mark_situations_rerun` once that completes.
    """
    reset_id = new_id("orst")

    expired = conn.execute(text(
        "update temporary_memories set active = false, expires_at = least(expires_at, :at) "
        "where org_id = :o and active and created_at < :at"),
        {"o": org_id, "at": at}).rowcount

    conn.execute(text(
        "insert into organization_resets (org_id, reset_id, reason, triggered_by, "
        "adaptive_expired, situations_rerun, created_at) "
        "values (:o, :id, :r, :a, :ex, false, :at)"),
        {"o": org_id, "id": reset_id, "r": reason, "a": actor, "ex": expired, "at": at})

    return {"reset_id": reset_id, "adaptive_expired": expired}


def mark_situations_rerun(conn, *, reset_id: str) -> None:
    conn.execute(text(
        "update organization_resets set situations_rerun = true where reset_id = :id"),
        {"id": reset_id})


def latest_reset_at(conn, *, org_id: str) -> datetime | None:
    """Most recent reset timestamp for the org, or None. Lets a reader ask "has this org pivoted
    since my evidence was gathered" without joining the full event log."""
    row = conn.execute(text(
        "select created_at from organization_resets where org_id = :o "
        "order by created_at desc limit 1"),
        {"o": org_id}).first()
    return row[0] if row else None


__all__ = ["apply_organization_reset", "mark_situations_rerun", "latest_reset_at"]

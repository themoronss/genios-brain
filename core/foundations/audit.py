"""Immutable audit log writer (per g-i-8).

HARD rules:
- Append-only (UPDATE/DELETE blocked at DB level once the audit_log table lands)
- NO content in audit rows — only refs (decision_id, source_item_id), counts, metadata
- Every: decision, data access, permission change, override → row inserted

Full audit_log schema + partitioning lands in g-i-8 phase. This Phase 1 stub
provides the writer API so other modules can call it from day one — it logs
via telemetry until the table exists, then will switch to DB insert without
caller changes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from core.foundations.telemetry import get_logger

log = get_logger(__name__)

ActorType = Literal["user", "agent", "system"]
Action = Literal[
    "decision_made",
    "data_accessed",
    "permission_changed",
    "override_captured",
    "module_activated",
    "module_deactivated",
    "scope_granted",
    "scope_revoked",
    "secret_accessed",
    "config_changed",
]


def record(
    *,
    org_id: str,
    actor_type: ActorType,
    actor_id: str,
    action: Action,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an audit event.

    `metadata` may contain refs and counts only — NEVER content.
    Caller is responsible for not putting raw bodies/secrets here; the writer
    does not inspect the dict (trust at the call site, enforced by code review).
    """
    log.info(
        "audit",
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
        ts=datetime.now(UTC).isoformat(),
    )

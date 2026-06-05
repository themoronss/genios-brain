"""Immutable audit log writer (per g-i-8).

HARD rules:
- Append-only: UPDATE/DELETE blocked at DB layer (revoke privilege in migration)
- NO content in audit rows — only refs (decision_id, source_item_id), counts, metadata
- Every: decision, data access, permission change, override → row inserted

Two write paths:
1. `record(...)`         — log-only (no session needed; survives before DB exists)
2. `record_db(session)`  — log + persist a row in `audit_log`

The dual API lets early-boot code (config load, encryption init) call `record()`
before a DB session exists, while production paths call `record_db(session)` to
get the immutable persisted trail.

Query side: `query_events(session, ...)` for the audit-API.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.metrics_store import AuditLogRow
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
    "data_subject_access",
    "data_subject_erasure",
    "retention_swept",
    # Auth lifecycle — recorded so security review can answer
    # "kab login hua, kahaan se, kab logout" without grepping app logs.
    "user_signed_up",
    "user_logged_in",
    "user_logged_out",
    "login_failed",
]


# Caller must NOT put content here. Code-review enforced; the writer does not
# inspect the dict beyond logging. Common refs: decision_id, source_item_id,
# counts (n_records, drop_count), policy outcomes (route, scope_level).
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
    """Persist an immutable audit row + emit a log line.

    Opens its own short-lived session so callers without a session in scope
    (background jobs, sync workers, persona seeders) still get a DB row.
    Failing to persist must NEVER raise into the caller — audit is a side
    effect of the business operation, not a precondition. The log line still
    fires so the event is observable in stderr/journald even if the DB
    write fails.

    For callers that already hold a session and want the audit row to
    commit atomically with their business mutation, use `record_db(session)`
    instead.
    """
    ts = datetime.now(UTC)
    log.info(
        "audit",
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
        ts=ts.isoformat(),
    )
    try:
        # Lazy import — avoids a circular at module load (audit is imported
        # by code that runs during db.py initialisation).
        from core.foundations.db import get_session

        with get_session() as s:
            s.add(
                AuditLogRow(
                    org_id=org_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    metadata_jsonb=dict(metadata or {}),
                    timestamp=ts,
                )
            )
            s.commit()
    except Exception as exc:
        # Audit write must not break the calling business op. Surface in
        # logs so a stderr/journald grep still shows the failure.
        log.warning(
            "audit_persist_failed",
            action=action,
            target_type=target_type,
            target_id=target_id,
            error=str(exc),
        )


def record_db(
    session: Session,
    *,
    org_id: str,
    actor_type: ActorType,
    actor_id: str,
    action: Action,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any] | None = None,
) -> AuditLogRow:
    """Log + persist an immutable audit row. Returns the inserted row.

    Caller commits the surrounding session — this function only flushes so the
    PK is populated for chained references.
    """
    row = AuditLogRow(
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_jsonb=dict(metadata or {}),
        timestamp=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    log.info(
        "audit_persisted",
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        audit_id=row.id,
        ts=row.timestamp.isoformat(),
    )
    return row


def query_events(
    session: Session,
    *,
    org_id: str,
    action: Action | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 200,
) -> Sequence[AuditLogRow]:
    """Read-side for the audit API. Always org-scoped (cross-org leaks blocked here)."""
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    stmt = select(AuditLogRow).where(AuditLogRow.org_id == org_id)
    if action is not None:
        stmt = stmt.where(AuditLogRow.action == action)
    if target_type is not None:
        stmt = stmt.where(AuditLogRow.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(AuditLogRow.target_id == target_id)
    if actor_id is not None:
        stmt = stmt.where(AuditLogRow.actor_id == actor_id)
    if since is not None:
        stmt = stmt.where(AuditLogRow.timestamp >= since)
    if until is not None:
        stmt = stmt.where(AuditLogRow.timestamp <= until)
    stmt = stmt.order_by(AuditLogRow.timestamp.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())

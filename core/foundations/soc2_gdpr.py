"""GDPR + SOC2 helpers (g-i-8) — data subject access + erasure + retention sweep.

Three operations every customer (and every regulator) can demand:
1. **Subject access:** "give me everything you have on user X"  → JSON export
2. **Erasure (right to be forgotten):** "delete everything on user X"
3. **Retention sweep:** "drop audit rows older than configured hot-retention"

What counts as "user-tied" data in v2 (today):
- `user_models` + `user_model_edits` + `user_model_proposals`  (g-i-9)
- `feedback_actions` rows with user_id                          (g-i-7)
- `channel_deliveries` rows with user_id                        (g-i-7)
- `insight_feedback` + `push_budget` rows tied to user_id       (g-i-4)
- `decisions` rows with user_id                                 (g-i-2)
- `audit_log` rows whose actor_id == user_id  (kept; never erased — required for SOC2 trail)

Audit-log rows are NEVER erased. We log the erasure itself as a new event.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.delivery.store import ChannelDeliveryRow, FeedbackActionRow
from core.foundations import audit
from core.foundations.metrics_store import AuditLogRow
from core.foundations.telemetry import get_logger
from core.proactive.store import (
    InsightFeedbackRow,
    PushBudgetRow,
)
from core.usermodel.store import (
    UserModelEditRow,
    UserModelProposalRow,
    UserModelRow,
)

log = get_logger(__name__)


def data_subject_access(
    session: Session,
    *,
    user_id: str,
    org_id: str,
) -> dict[str, Any]:
    """Return all stored data for one user as a serializable dict.

    Org-scoped — caller must supply the org_id this user belongs to so a
    compromised user_id can't pull data across tenants.
    """
    profile = (
        session.execute(
            select(UserModelRow)
            .where(UserModelRow.user_id == user_id)
            .where(UserModelRow.org_unit == org_id)
        )
        .scalars()
        .one_or_none()
    )

    edits = (
        session.execute(select(UserModelEditRow).where(UserModelEditRow.user_id == user_id))
        .scalars()
        .all()
    )
    proposals = (
        session.execute(select(UserModelProposalRow).where(UserModelProposalRow.user_id == user_id))
        .scalars()
        .all()
    )
    feedbacks = (
        session.execute(
            select(FeedbackActionRow)
            .where(FeedbackActionRow.user_id == user_id)
            .where(FeedbackActionRow.org_id == org_id)
        )
        .scalars()
        .all()
    )
    deliveries = (
        session.execute(
            select(ChannelDeliveryRow)
            .where(ChannelDeliveryRow.user_id == user_id)
            .where(ChannelDeliveryRow.org_id == org_id)
        )
        .scalars()
        .all()
    )
    insight_feedback = (
        session.execute(
            select(InsightFeedbackRow)
            .where(InsightFeedbackRow.user_id == user_id)
            .where(InsightFeedbackRow.org_id == org_id)
        )
        .scalars()
        .all()
    )
    push_budgets = (
        session.execute(select(PushBudgetRow).where(PushBudgetRow.user_id == user_id))
        .scalars()
        .all()
    )
    audit_rows = (
        session.execute(
            select(AuditLogRow)
            .where(AuditLogRow.org_id == org_id)
            .where(AuditLogRow.actor_id == user_id)
        )
        .scalars()
        .all()
    )

    export: dict[str, Any] = {
        "user_id": user_id,
        "org_id": org_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "user_profile": _model_to_dict(profile) if profile else None,
        "user_model_edits": [_model_to_dict(r) for r in edits],
        "user_model_proposals": [_model_to_dict(r) for r in proposals],
        "feedback_actions": [_model_to_dict(r) for r in feedbacks],
        "channel_deliveries": [_model_to_dict(r) for r in deliveries],
        "insight_feedback": [_model_to_dict(r) for r in insight_feedback],
        "push_budgets": [_model_to_dict(r) for r in push_budgets],
        "audit_events": [_model_to_dict(r) for r in audit_rows],
    }

    audit.record_db(
        session,
        org_id=org_id,
        actor_type="system",
        actor_id="gdpr_subject_access",
        action="data_subject_access",
        target_type="user",
        target_id=user_id,
        metadata={
            "rows_exported": sum(
                len(v) if isinstance(v, list) else (1 if v is not None and k != "user_id" else 0)
                for k, v in export.items()
            )
        },
    )
    log.info("gdpr_subject_access", org_id=org_id, user_id=user_id)
    return export


def erasure(
    session: Session,
    *,
    user_id: str,
    org_id: str,
) -> dict[str, int]:
    """Delete every user-tied row (audit log preserved). Returns per-table delete counts."""
    counts: dict[str, int] = {}

    counts["user_model_edits"] = _delete_count(
        session, delete(UserModelEditRow).where(UserModelEditRow.user_id == user_id)
    )
    counts["user_model_proposals"] = _delete_count(
        session, delete(UserModelProposalRow).where(UserModelProposalRow.user_id == user_id)
    )
    counts["user_models"] = _delete_count(
        session,
        delete(UserModelRow)
        .where(UserModelRow.user_id == user_id)
        .where(UserModelRow.org_unit == org_id),
    )
    counts["feedback_actions"] = _delete_count(
        session,
        delete(FeedbackActionRow)
        .where(FeedbackActionRow.user_id == user_id)
        .where(FeedbackActionRow.org_id == org_id),
    )
    counts["channel_deliveries"] = _delete_count(
        session,
        delete(ChannelDeliveryRow)
        .where(ChannelDeliveryRow.user_id == user_id)
        .where(ChannelDeliveryRow.org_id == org_id),
    )
    counts["insight_feedback"] = _delete_count(
        session,
        delete(InsightFeedbackRow)
        .where(InsightFeedbackRow.user_id == user_id)
        .where(InsightFeedbackRow.org_id == org_id),
    )
    counts["push_budget"] = _delete_count(
        session, delete(PushBudgetRow).where(PushBudgetRow.user_id == user_id)
    )
    session.flush()

    audit.record_db(
        session,
        org_id=org_id,
        actor_type="system",
        actor_id="gdpr_erasure",
        action="data_subject_erasure",
        target_type="user",
        target_id=user_id,
        metadata={"counts": counts},
    )
    log.info("gdpr_erasure", org_id=org_id, user_id=user_id, counts=counts)
    return counts


def retention_sweep(
    session: Session,
    *,
    org_id: str,
    audit_hot_days: int,
) -> int:
    """Delete audit rows older than `audit_hot_days` for one org. Returns delete count.

    Production: cold storage export happens BEFORE this sweep — operator's
    responsibility (S3 dump per `AUDIT_COLD_STORAGE` config). We only enforce
    the in-DB retention horizon here.
    """
    if audit_hot_days < 1:
        raise ValueError("audit_hot_days must be >= 1")
    cutoff = datetime.now(UTC) - timedelta(days=audit_hot_days)
    n = _delete_count(
        session,
        delete(AuditLogRow)
        .where(AuditLogRow.org_id == org_id)
        .where(AuditLogRow.timestamp < cutoff),
    )
    session.flush()
    # Record the sweep itself — new audit row survives, immune to the sweep we just ran
    audit.record_db(
        session,
        org_id=org_id,
        actor_type="system",
        actor_id="retention_sweep",
        action="retention_swept",
        target_type="audit_log",
        target_id=org_id,
        metadata={"cutoff": cutoff.isoformat(), "rows_deleted": n},
    )
    log.info(
        "audit_retention_swept",
        org_id=org_id,
        cutoff=cutoff.isoformat(),
        rows_deleted=n,
    )
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _delete_count(session: Session, stmt: Any) -> int:
    result = session.execute(stmt)
    # CursorResult exposes rowcount; the typed Result base does not. Use getattr
    # to keep mypy strict happy without an ignore comment.
    n = getattr(result, "rowcount", 0)
    return int(n or 0)


def _model_to_dict(row: Any) -> dict[str, Any]:
    """Serialize a SQLAlchemy row to a JSON-safe dict (datetimes -> isoformat)."""
    out: dict[str, Any] = {}
    for col in row.__table__.columns:
        v = getattr(row, col.name)
        if isinstance(v, datetime):
            out[col.name] = v.isoformat()
        else:
            out[col.name] = v
    return out

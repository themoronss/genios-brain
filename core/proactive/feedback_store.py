"""Per-user feedback history for suppression learning.

Per MD g-i-4 §1.2.1:
    on user action {acted, dismissed, snoozed, never_show}:
        store (insight_signature, action)
        learn down-weight: insights similar to dismissed -> suppression_factor < 1
        "never_show" on signature -> hard mute that signature
    suppression is per-user / per-org-unit
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.proactive.store import InsightFeedbackRow

log = get_logger(__name__)


FeedbackAction = Literal["acted", "dismissed", "snoozed", "never_show"]


class FeedbackStore:
    """Per-user feedback read + write. Thin wrapper around InsightFeedbackRow."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        org_id: str,
        user_id: str,
        signature_hash: str,
        action: FeedbackAction,
    ) -> InsightFeedbackRow:
        """Persist a feedback signal. Audit-logged."""
        row = InsightFeedbackRow(
            org_id=org_id,
            user_id=user_id,
            signature_hash=signature_hash,
            action=action,
        )
        self._session.add(row)
        self._session.flush()

        audit.record(
            org_id=org_id,
            actor_type="user",
            actor_id=user_id,
            action="override_captured" if action in ("acted", "dismissed") else "data_accessed",
            target_type="insight_signature",
            target_id=signature_hash,
            metadata={"feedback_action": action},
        )
        log.info(
            "feedback_recorded",
            org_id=org_id,
            user_id=user_id,
            signature_hash=signature_hash,
            action=action,
        )
        return row

    def last_action(
        self, *, org_id: str, user_id: str, signature_hash: str
    ) -> FeedbackAction | None:
        """Latest feedback action for (user, signature) — None if no history."""
        row = self._session.execute(
            select(InsightFeedbackRow)
            .where(InsightFeedbackRow.org_id == org_id)
            .where(InsightFeedbackRow.user_id == user_id)
            .where(InsightFeedbackRow.signature_hash == signature_hash)
            .order_by(InsightFeedbackRow.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return row.action  # type: ignore[return-value]

    def action_count(
        self, *, org_id: str, user_id: str, signature_hash: str, action: FeedbackAction
    ) -> int:
        """How many times has this user taken `action` on `signature`?"""
        rows = self._session.execute(
            select(InsightFeedbackRow)
            .where(InsightFeedbackRow.org_id == org_id)
            .where(InsightFeedbackRow.user_id == user_id)
            .where(InsightFeedbackRow.signature_hash == signature_hash)
            .where(InsightFeedbackRow.action == action)
        ).all()
        return len(rows)


# Module-level alias so callers don't need to import datetime here
_ = (datetime, UTC)

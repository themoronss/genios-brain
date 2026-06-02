"""SQLAlchemy models for g-i-4 — created by migration 0006.

4 tables:
- insights              — generated insights (with scores + route)
- insight_feedback      — per-user 👍/👎/snooze/never_show signals
- push_budget           — per-user per-day interrupt budget
- workflow_baselines    — rolling org channel/cadence/topic mix for drift detection
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class InsightRow(Base):
    """Generated insight. One row per fired insight (before dedupe suppression)."""

    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    primary_entity: Mapped[str] = mapped_column(String(255), nullable=False)
    root_cause_edge: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    derivation_chain_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    foresight_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    scores_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    grounding_refs_jsonb: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    signature_hash: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    delivery_route: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_insights_org_signature", "org_id", "signature_hash"),
        Index("ix_insights_org_created", "org_id", "created_at"),
    )


class InsightFeedbackRow(Base):
    """Per-user feedback on a specific insight signature.

    Per MD: per-user / per-org-unit suppression. never_show -> hard mute.
    """

    __tablename__ = "insight_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature_hash: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="acted | dismissed | snoozed | never_show"
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)


class PushBudgetRow(Base):
    """Per-user per-day interrupt budget (anti-fatigue, per MD §1.2.2 + GENIOS_V2_PLAN)."""

    __tablename__ = "push_budget"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    interrupts_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_allowed: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    __table_args__ = (Index("ix_push_budget_user_date", "user_id", "date", unique=True),)


class WorkflowBaselineRow(Base):
    """Rolling baseline of an org's channel/cadence/topic mix for drift detection.

    Per MD update §1.1.3: when workflow shifts >theta_drift -> recalibrate priorities.
    """

    __tablename__ = "workflow_baselines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dim: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="channel_mix | cadence | topic_mix"
    )
    baseline_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    window_start: Mapped[datetime] = mapped_column(nullable=False)
    window_end: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_baselines_org_dim", "org_id", "dim"),)


# Unused-imports guards
_ = Text  # may be used by future fields

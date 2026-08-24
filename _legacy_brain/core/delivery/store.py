"""SQLAlchemy models for g-i-7 — created by migration 0009.

4 tables:
- agent_registry         — registered agent identities + granted scopes
- agent_calls            — audit of every agent pull-API call
- channel_deliveries     — audit of every human-facing push
- feedback_actions       — raw 👍/👎/edit signals (transformed into Corrections)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AgentRegistryRow(Base):
    """Registered agent that may pull intelligence + receive push insights."""

    __tablename__ = "agent_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_scopes_jsonb: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    active_modules_jsonb: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    api_key_ref: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("secrets_ref.id", ondelete="SET NULL"),
        nullable=True,
        comment="Vault handle (reuses g-i-1 secrets table)",
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    last_seen: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_agent_registry_org_agent", "org_id", "agent_id", unique=True),)


class AgentCallRow(Base):
    """Audit of every agent pull-API call."""

    __tablename__ = "agent_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    outcome: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="ok | scope_denied | budget_halted | error",
    )
    timestamp: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)


class ChannelDeliveryRow(Base):
    """Audit of every human-facing push (Slack/email/webhook/dashboard)."""

    __tablename__ = "channel_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="slack | email | webhook | dashboard"
    )
    insight_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="sent",
        comment="sent | failed | suppressed",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeedbackActionRow(Base):
    """Raw 👍/👎/edit/snooze/never_show. Transformed into Corrections (g-i-3) by feedback_capture."""

    __tablename__ = "feedback_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    insight_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="thumbs_up | thumbs_down | edit | snooze | never_show",
    )
    edit_diff_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    correction_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="If transformed -> id of created CorrectionRow",
    )
    timestamp: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

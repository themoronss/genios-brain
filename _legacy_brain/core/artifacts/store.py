"""SQLAlchemy models for g-i-6 — created by migration 0007.

2 tables:
- artifacts                 — finalized briefs/reports with trace + body
- ungrounded_rejections     — observability: every narrator rejection logged
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


class ArtifactRow(Base):
    """A finalized artifact. Trace + body + counterfactuals + uncertainty all preserved."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    trace_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    counterfactuals_jsonb: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    uncertainty_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generated_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    generated_by_module: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_artifacts_org_decision", "org_id", "decision_id"),
        Index("ix_artifacts_org_generated", "org_id", "generated_at"),
    )


class UngroundedRejectionRow(Base):
    """Observability — every narrator rejection logged."""

    __tablename__ = "ungrounded_rejections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rejected_claim: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

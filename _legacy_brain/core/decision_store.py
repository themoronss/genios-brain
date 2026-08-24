"""DB model for emitted Decisions (g-i-2 EMIT step).

Per MD g-i-2 + GENIOS_V2_PLAN.md migration 0004:
- One row per decision; full derivation chain + grounding refs + route
- as_of_version pinned for replay
- triggered_by tracks query | proactive_scan | webhook
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DecisionRow(Base):
    """An emitted engine decision. Persisted before delivery for replay + audit."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    derivation_chain_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    path: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="symbolic | neural | hybrid"
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_breakdown_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    grounding_refs_jsonb: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    route: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="autonomous | notify | flag"
    )
    as_of_version: Mapped[int] = mapped_column(nullable=False, default=0)
    triggered_by: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="query",
        comment="query | proactive_scan | webhook",
    )
    module_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_decisions_org_created", "org_id", "created_at"),
        Index("ix_decisions_org_route", "org_id", "route"),
        Index("ix_decisions_org_module", "org_id", "module_id"),
    )

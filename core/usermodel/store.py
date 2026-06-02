"""SQLAlchemy models for g-i-9 — created by migration 0008.

3 tables (thin per design):
- user_models            — one row per user (kilobytes; field bodies as JSONB)
- user_model_edits       — bounded rolling window of edits (raw signals for re-distill)
- user_model_proposals   — big inferred shifts pending user confirm
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UserModelRow(Base):
    """One row per user. Body fields stored as JSONB for cheap evolution."""

    __tablename__ = "user_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    org_unit: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    voice_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    decision_policy_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    process_habits_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    priorities_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    relationships_jsonb: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    red_lines_jsonb: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    field_meta_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)


class UserModelEditRow(Base):
    """Bounded rolling window of raw edits per field. Older entries dropped after distill.

    Per MD: keep last K edits per field (default K=20). Older raw edits are
    discarded by the distill pipeline once the conclusion has been updated.
    """

    __tablename__ = "user_model_edits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    edit_diff_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_correction_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="Links to corrections (g-i-3) when distilling from a structured override",
    )
    applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True once this edit has been folded into the field's conclusion",
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_user_model_edits_user_field", "user_id", "field"),)


class UserModelProposalRow(Base):
    """Big inferred shifts awaiting user confirm. Per MD: propose-confirm, never silent."""

    __tablename__ = "user_model_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    current_value_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    proposed_value_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    signal_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        comment="pending | approved | rejected",
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

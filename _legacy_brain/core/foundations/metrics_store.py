"""SQLAlchemy models for g-i-8 foundations metrics.

5 tables (migration 0010):
- audit_log              — immutable append-only event log (no content, refs+counts only)
- intervention_metrics   — THE North Star: per-org/per-module/per-day rollup
- calibration_metrics    — ECE/Brier per confidence bucket, weekly window
- resolution_metrics     — symbolic/neural/hybrid path counts (engine health)
- roi_metrics            — autonomous value vs LLM+infra cost per day

Postgres uses partitioning on audit_log (by month); SQLite (tests) uses a plain
table with the same shape. Partitioning is configured in the migration, not here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    Float,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLogRow(Base):
    """Immutable audit event. UPDATE/DELETE blocked at DB layer (trigger in 0010).

    Caller MUST NOT put content in `metadata_jsonb` — refs + counts only.
    The ORM model uses `id` as the sole PK so SQLite tests work; the migration
    rewrites the table as PARTITION BY RANGE (timestamp) on Postgres, where
    the partitioning key must be in the PK — that compound PK is created via
    raw SQL in the migration and only applies in production.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Identity(always=False),
        primary_key=True,
        autoincrement=True,
    )
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="user | agent | system"
    )
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    timestamp: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_org_ts", "org_id", "timestamp"),
        Index("ix_audit_org_action_ts", "org_id", "action", "timestamp"),
        Index("ix_audit_target", "target_type", "target_id"),
    )


class InterventionMetricRow(Base):
    """Daily rollup: human override rate per org/module. THE North Star.

    intervention_rate = human_overrides_count / max(1, total_decisions).
    Trend DOWN over time = thesis alive. Trend UP = engine getting worse.
    """

    __tablename__ = "intervention_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_decisions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    autonomous_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notify_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flag_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_overrides_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intervention_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "module_id", "date", name="uq_intervention_org_module_date"),
        Index("ix_intervention_org_date", "org_id", "date"),
    )


class CalibrationMetricRow(Base):
    """ECE / Brier per confidence bucket per module per window.

    Bucket boundaries are 0.0-0.1, 0.1-0.2, ... 0.9-1.0 (10 fixed buckets).
    predicted_bucket stores the bucket label (e.g. "0.7-0.8").
    """

    __tablename__ = "calibration_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    bucket_lower: Mapped[float] = mapped_column(Float, nullable=False)
    bucket_upper: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mean_predicted_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_outcome_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    brier_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ece_contribution: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Weighted |predicted - observed| contribution to org-level ECE",
    )
    computed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        Index(
            "ix_calib_org_module_window",
            "org_id",
            "module_id",
            "window_start",
            "window_end",
        ),
    )


class ResolutionMetricRow(Base):
    """Engine health: how often did symbolic alone suffice vs needing neural?

    Per MD g-i-2: symbolic_resolution_rate should TREND UP as the graph fills.
    """

    __tablename__ = "resolution_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    symbolic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    neural_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hybrid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    symbolic_resolution_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "module_id", "date", name="uq_resolution_org_module_date"),
    )


class RoiMetricRow(Base):
    """Value delivered by autonomous actions vs LLM+infra cost (per MD §1).

    `estimated_value_usd` is module-specific — caller supplies the heuristic
    (e.g., Sales module: $X per qualified-lead surfaced ahead of human triage).
    """

    __tablename__ = "roi_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    autonomous_actions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_value_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    infra_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    roi_ratio: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="value / (llm_cost + infra_cost); inf if costs == 0",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "module_id", "date", name="uq_roi_org_module_date"),
    )

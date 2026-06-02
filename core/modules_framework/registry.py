"""Per-org module activation registry.

Per MD g-i-5 §5.1.2:
- Enabling/disabling a module is permission-audited (who, when, why)
- A module enabled for org A is INVISIBLE to org B (isolation)
- Misconfig must FAIL CLOSED (disabled), never fail open

Tables (created by migration 0005):
- modules                    catalog of installed module versions
- org_modules                per-org activation rows (ACCESS CONTROL)
- module_activations_audit   immutable audit log
- module_golden_runs         golden test results
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from core.foundations import audit
from core.foundations.db import Base
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────────
# Tables
# ─────────────────────────────────────────────────────────────────────────────


class ModuleRow(Base):
    """Catalog of installed module versions."""

    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    golden_set_path: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_modules_module_version", "module_id", "version", unique=True),)

    org_activations: Mapped[list[OrgModuleRow]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )


class OrgModuleRow(Base):
    """Per-org activation (ACCESS CONTROL). A row's existence == module enabled."""

    __tablename__ = "org_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module_pk: Mapped[str] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    activated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    deactivated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    module: Mapped[ModuleRow] = relationship(back_populates="org_activations")

    __table_args__ = (Index("ix_org_modules_org_module", "org_id", "module_pk", unique=True),)


class ModuleActivationAuditRow(Base):
    """Immutable audit of enable / disable / swap events."""

    __tablename__ = "module_activations_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="enable | disable | swap"
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)


class ModuleGoldenRunRow(Base):
    """Golden test results — one row per (module, version) test run."""

    __tablename__ = "module_golden_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    ran_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    threshold: Mapped[float] = mapped_column(nullable=False)
    metrics_jsonb: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


class RegistryError(Exception):
    """Activation refused (fail closed) — module unknown, golden failed, etc."""


@dataclass(frozen=True)
class ModuleActivation:
    """Snapshot of one org-module activation."""

    org_id: str
    module_id: str
    version: str
    enabled: bool
    activated_by: str


class Registry:
    """Read-side queries over module activations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_org(self, org_id: str) -> list[ModuleActivation]:
        """All currently-active modules for an org. Isolation: row for org A invisible to org B."""
        rows = (
            self._session.query(OrgModuleRow)
            .join(ModuleRow, OrgModuleRow.module_pk == ModuleRow.id)
            .filter(OrgModuleRow.org_id == org_id)
            .filter(OrgModuleRow.enabled.is_(True))
            .all()
        )
        return [
            ModuleActivation(
                org_id=r.org_id,
                module_id=r.module.module_id,
                version=r.module.version,
                enabled=r.enabled,
                activated_by=r.activated_by,
            )
            for r in rows
        ]

    def is_enabled(self, *, org_id: str, module_id: str) -> bool:
        """Check if a specific module is enabled for an org."""
        for activation in self.list_for_org(org_id):
            if activation.module_id == module_id:
                return True
        return False


def activate_module(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    version: str,
    actor: str,
    reason: str | None = None,
) -> ModuleActivation:
    """Enable a module for an org. Fails closed if the (module_id, version) isn't in catalog.

    Per MD: golden test MUST pass before calling this. Caller responsibility — registry
    only persists; doesn't re-run golden.
    """
    module_row = (
        session.query(ModuleRow)
        .filter_by(module_id=module_id, version=version, active=True)
        .one_or_none()
    )
    if module_row is None:
        log.warning(
            "module_activation_unknown_module",
            module_id=module_id,
            version=version,
            org_id=org_id,
        )
        raise RegistryError(
            f"Module {module_id}@{version} not in catalog or inactive — fail closed"
        )

    existing = (
        session.query(OrgModuleRow).filter_by(org_id=org_id, module_pk=module_row.id).one_or_none()
    )
    if existing is not None:
        if existing.enabled:
            return ModuleActivation(
                org_id=org_id,
                module_id=module_id,
                version=version,
                enabled=True,
                activated_by=existing.activated_by,
            )
        # Re-enable
        existing.enabled = True
        existing.activated_by = actor
        existing.activated_at = _utcnow()
        existing.deactivated_at = None
        existing.deactivated_by = None
    else:
        existing = OrgModuleRow(
            org_id=org_id,
            module_pk=module_row.id,
            enabled=True,
            activated_by=actor,
        )
        session.add(existing)
        session.flush()

    _audit_activation(
        session,
        org_id=org_id,
        module_id=module_id,
        version=version,
        action="enable",
        actor=actor,
        reason=reason,
    )

    return ModuleActivation(
        org_id=org_id,
        module_id=module_id,
        version=version,
        enabled=True,
        activated_by=actor,
    )


def deactivate_module(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    actor: str,
    reason: str | None = None,
) -> None:
    """Disable a module for an org. Sets enabled=False; audit-logged."""
    row = (
        session.query(OrgModuleRow)
        .join(ModuleRow, OrgModuleRow.module_pk == ModuleRow.id)
        .filter(OrgModuleRow.org_id == org_id)
        .filter(ModuleRow.module_id == module_id)
        .filter(OrgModuleRow.enabled.is_(True))
        .one_or_none()
    )
    if row is None:
        return  # idempotent — already off

    row.enabled = False
    row.deactivated_by = actor
    row.deactivated_at = _utcnow()

    _audit_activation(
        session,
        org_id=org_id,
        module_id=module_id,
        version=row.module.version,
        action="disable",
        actor=actor,
        reason=reason,
    )


def register_module_version(
    session: Session,
    *,
    module_id: str,
    version: str,
    manifest_jsonb: dict[str, Any],
    golden_set_path: str,
) -> ModuleRow:
    """Add a module version to the catalog (idempotent on (module_id, version))."""
    existing = (
        session.query(ModuleRow).filter_by(module_id=module_id, version=version).one_or_none()
    )
    if existing is not None:
        return existing
    row = ModuleRow(
        module_id=module_id,
        version=version,
        manifest_jsonb=manifest_jsonb,
        golden_set_path=golden_set_path,
        active=True,
    )
    session.add(row)
    session.flush()
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _audit_activation(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    version: str,
    action: str,
    actor: str,
    reason: str | None,
) -> None:
    row = ModuleActivationAuditRow(
        org_id=org_id,
        module_id=module_id,
        version=version,
        action=action,
        actor=actor,
        reason=reason,
    )
    session.add(row)
    session.flush()
    audit.record(
        org_id=org_id,
        actor_type="user",
        actor_id=actor,
        action="module_activated" if action == "enable" else "module_deactivated",
        target_type="module",
        target_id=f"{module_id}@{version}",
        metadata={"reason": reason},
    )


# `Sequence` is exported for future bulk operations
_ = Sequence

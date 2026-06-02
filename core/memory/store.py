"""DB models + CRUD for g-i-1 operational metadata.

Tables (NO content — only operational state):
- connections        one row per connected source instance
- secrets_ref        pointer to encrypted secret (actual value in DB column via secrets.py)
- cursors            delta-detection state per connection
- source_mappings    frozen mapping artifacts (custom adapters)
- scope_grants       audit + enforcement of read scopes

Per-org isolation: every row has org_id; queries always filter by it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.foundations.db import Base

if TYPE_CHECKING:
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Connection(Base):
    """One connected source instance per row.

    A customer can have multiple connections of the same source_type
    (e.g. two Gmail accounts).
    """

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Provider-side identifier (e.g. workspace id, mailbox address)",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="pending | active | paused | error | revoked",
    )
    health_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="green",
        comment="green | yellow | red",
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    last_health_check_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    cursors: Mapped[list[CursorRow]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    mappings: Mapped[list[SourceMappingRow]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    secrets: Mapped[list[SecretRef]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    scope_grants: Mapped[list[ScopeGrant]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_connections_org_source", "org_id", "source_type"),
    )


class SecretRef(Base):
    """Pointer + encrypted blob for a customer credential.

    Value is encrypted via core.foundations.encryption.encrypt() before INSERT.
    Use core.memory.secrets.put/get to interact (handles encrypt/decrypt).
    """

    __tablename__ = "secrets_ref"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    secret_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="oauth_access | oauth_refresh | api_key | service_account | basic | jwt | mtls_cert",
    )
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    connection: Mapped[Connection] = relationship(back_populates="secrets")


class CursorRow(Base):
    """Delta-detection cursor per connection."""

    __tablename__ = "cursors"

    connection_id: Mapped[str] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), primary_key=True
    )
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cursor_value: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="native | updated_at | content_hash",
    )
    last_sync_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    items_pulled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    connection: Mapped[Connection] = relationship(back_populates="cursors")


class SourceMappingRow(Base):
    """Frozen SourceMapping artifact (custom adapters; known adapters skip this)."""

    __tablename__ = "source_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mapping_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    source_confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)

    connection: Mapped[Connection] = relationship(back_populates="mappings")


class ScopeGrant(Base):
    """One read-scope grant per row. Multiple per connection are AND-combined."""

    __tablename__ = "scope_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    granted_by: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    scope_drops_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Cumulative count of records dropped by this scope (observability)",
    )

    connection: Mapped[Connection] = relationship(back_populates="scope_grants")

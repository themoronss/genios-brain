"""SQLAlchemy models for human-user auth (signup/login/JWT).

3 tables:
- users        one row per human; password_hash stored bcrypt
- orgs         organizations; created_by_user_id = founding admin
- org_members  user ↔ org membership with role (admin / member / viewer)

Auth flow (POST /auth/signup):
    1. user_row inserted (email unique)
    2. org_row inserted (org_name; created_by = user.id)
    3. org_member inserted with role=admin
    4. first API key minted via AgentRegistry + SecretRef
    5. JWT session token returned for the dashboard
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UserRow(Base):
    """One human user. Email is the natural unique key."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)


class OrgRow(Base):
    """Organization — owns memory, decisions, modules, etc.

    Note this is distinct from g-i-1's `connections.org_id` String FK — those
    were always free-form. This table now provides the authoritative org list.
    Per-org-isolated tables continue to use org_id as a string FK by convention.
    """

    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    plan: Mapped[str] = mapped_column(
        String(32), nullable=False, default="trial", comment="trial | paid | enterprise"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", comment="active | suspended | deleted"
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)


class OrgMemberRow(Base):
    """User ↔ Org join table with role."""

    __tablename__ = "org_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member", comment="admin | member | viewer"
    )
    joined_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
        Index("ix_org_members_user", "user_id"),
    )

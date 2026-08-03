"""Tests for registry activation + isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.modules_framework.isolation import IsolationError, IsolationGuard
from core.modules_framework.registry import (
    Registry,
    RegistryError,
    activate_module,
    deactivate_module,
    register_module_version,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _register_sales(session: Session) -> None:
    register_module_version(
        session,
        module_id="sales",
        version="1.0.0",
        manifest_jsonb={"id": "sales", "version": "1.0.0"},
        golden_set_path="evaluator.py",
    )
    session.flush()


# ── registry activation ────────────────────────────────────────────────────


@pytest.mark.unit
def test_activate_unknown_module_fails_closed(session: Session) -> None:
    """Per MD: misconfig MUST fail closed, never expose."""
    with pytest.raises(RegistryError):
        activate_module(
            session,
            org_id="org_a",
            module_id="nonexistent",
            version="1.0.0",
            actor="user:admin",
        )


@pytest.mark.unit
def test_activate_persists_and_lists(session: Session) -> None:
    _register_sales(session)
    activation = activate_module(
        session,
        org_id="org_a",
        module_id="sales",
        version="1.0.0",
        actor="user:admin",
        reason="onboarding",
    )
    session.commit()

    assert activation.module_id == "sales"
    assert activation.enabled is True

    listed = Registry(session).list_for_org("org_a")
    assert len(listed) == 1
    assert listed[0].module_id == "sales"


@pytest.mark.unit
def test_isolation_invisible_across_orgs(session: Session) -> None:
    """Per MD: module enabled for org A is INVISIBLE to org B."""
    _register_sales(session)
    activate_module(
        session,
        org_id="org_a",
        module_id="sales",
        version="1.0.0",
        actor="user:admin",
    )
    session.commit()

    assert Registry(session).is_enabled(org_id="org_a", module_id="sales") is True
    assert Registry(session).is_enabled(org_id="org_b", module_id="sales") is False


@pytest.mark.unit
def test_deactivate_makes_module_invisible(session: Session) -> None:
    _register_sales(session)
    activate_module(session, org_id="org_a", module_id="sales", version="1.0.0", actor="user:admin")
    session.commit()
    deactivate_module(session, org_id="org_a", module_id="sales", actor="user:admin")
    session.commit()

    assert Registry(session).is_enabled(org_id="org_a", module_id="sales") is False


@pytest.mark.unit
def test_idempotent_activation(session: Session) -> None:
    """Activating an already-enabled module returns existing activation cleanly."""
    _register_sales(session)
    a1 = activate_module(
        session, org_id="org_a", module_id="sales", version="1.0.0", actor="user:admin"
    )
    a2 = activate_module(
        session, org_id="org_a", module_id="sales", version="1.0.0", actor="user:admin"
    )
    session.commit()
    assert a1.enabled and a2.enabled


# ── IsolationGuard ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_isolation_guard_rejects_cross_org() -> None:
    guard = IsolationGuard(org_id="org_a", module_id="sales")
    with pytest.raises(IsolationError):
        guard.require_org("org_b")


@pytest.mark.unit
def test_isolation_guard_rejects_cross_module() -> None:
    guard = IsolationGuard(org_id="org_a", module_id="sales")
    with pytest.raises(IsolationError):
        guard.require_module("finance")


@pytest.mark.unit
def test_isolation_guard_accepts_matching() -> None:
    guard = IsolationGuard(org_id="org_a", module_id="sales")
    guard.require_both(org_id="org_a", module_id="sales")  # no exception


@pytest.mark.unit
def test_isolation_guard_rejects_empty_inputs() -> None:
    with pytest.raises(IsolationError):
        IsolationGuard(org_id="", module_id="sales")
    with pytest.raises(IsolationError):
        IsolationGuard(org_id="org_a", module_id="")

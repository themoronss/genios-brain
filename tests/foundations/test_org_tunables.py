"""Tests for the per-org tunable override store + resolver."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations import org_tunables
from core.foundations.db import Base
from core.memory.store import SecretRef  # noqa: F401 — loads FK target


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    org_tunables.clear_cache()


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.unit
def test_falls_back_to_module_default(session: Session) -> None:
    """No override + no caller default -> reads from config.py module."""
    val = org_tunables.get_tunable(session, org_id="o", key="N_MIN_EVIDENCE")
    assert val == 20  # core.foundations.config.N_MIN_EVIDENCE


@pytest.mark.unit
def test_caller_default_beats_module_default(session: Session) -> None:
    val = org_tunables.get_tunable(
        session, org_id="o", key="N_MIN_EVIDENCE", default=999
    )
    assert val == 999


@pytest.mark.unit
def test_override_beats_caller_and_module(session: Session) -> None:
    org_tunables.set_tunable(
        session, org_id="o", key="N_MIN_EVIDENCE", value=50, set_by="ops:alice"
    )
    session.commit()
    val = org_tunables.get_tunable(
        session, org_id="o", key="N_MIN_EVIDENCE", default=999
    )
    assert val == 50


@pytest.mark.unit
def test_override_org_isolated(session: Session) -> None:
    org_tunables.set_tunable(
        session, org_id="o1", key="N_MIN_EVIDENCE", value=50, set_by="ops:alice"
    )
    session.commit()
    assert org_tunables.get_tunable(session, org_id="o1", key="N_MIN_EVIDENCE") == 50
    assert org_tunables.get_tunable(session, org_id="o2", key="N_MIN_EVIDENCE") == 20


@pytest.mark.unit
def test_set_then_update(session: Session) -> None:
    org_tunables.set_tunable(
        session, org_id="o", key="N_MIN_EVIDENCE", value=50, set_by="ops:alice"
    )
    session.commit()
    org_tunables.set_tunable(
        session,
        org_id="o",
        key="N_MIN_EVIDENCE",
        value=100,
        set_by="ops:bob",
        reason="paid tier bump",
    )
    session.commit()
    val = org_tunables.get_tunable(session, org_id="o", key="N_MIN_EVIDENCE")
    assert val == 100
    overrides = org_tunables.list_overrides(session, org_id="o")
    assert overrides == {"N_MIN_EVIDENCE": 100}


@pytest.mark.unit
def test_delete_falls_back_to_default(session: Session) -> None:
    org_tunables.set_tunable(
        session, org_id="o", key="N_MIN_EVIDENCE", value=50, set_by="ops"
    )
    session.commit()
    assert org_tunables.delete_tunable(session, org_id="o", key="N_MIN_EVIDENCE", set_by="ops")
    session.commit()
    val = org_tunables.get_tunable(session, org_id="o", key="N_MIN_EVIDENCE")
    assert val == 20  # back to module default


@pytest.mark.unit
def test_delete_unknown_returns_false(session: Session) -> None:
    assert (
        org_tunables.delete_tunable(session, org_id="o", key="MISSING", set_by="ops")
        is False
    )


@pytest.mark.unit
def test_unknown_key_with_no_defaults_raises(session: Session) -> None:
    with pytest.raises(ValueError):
        org_tunables.get_tunable(session, org_id="o", key="THIS_KEY_DOES_NOT_EXIST")


@pytest.mark.unit
def test_json_value_round_trip(session: Session) -> None:
    """Values can be any JSON shape — dicts/lists/scalars."""
    org_tunables.set_tunable(
        session,
        org_id="o",
        key="CRON_INTERVAL_HOURS",
        value={"sales": 1, "default": 12},
        set_by="ops",
    )
    session.commit()
    val = org_tunables.get_tunable(session, org_id="o", key="CRON_INTERVAL_HOURS")
    assert val == {"sales": 1, "default": 12}

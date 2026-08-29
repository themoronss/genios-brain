"""organization_reset — the pivot primitive, against real PostgreSQL (rolled back)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.feedback import reset

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn(live_db_url):
    try:
        from genios_engine.platform.db import get_engine
        # The scratch database when one is set — never the configured (production) one.
        # See tests/conftest.py::live_test_database_url for why that ordering matters.
        url = live_db_url
        if not url:
            pytest.skip("no database configured")
        c = get_engine(url).connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    tx = c.begin()
    if not c.execute(text("select to_regclass('public.organization_resets')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0059 not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _seed_lease(c, org, *, memory_id, created_at, expires_at):
    c.execute(text(
        "insert into temporary_memories (org_id, memory_id, learning_id, subject, value, "
        "visibility_scope, visibility, expires_at, active, created_at) "
        "values (:o, :m, 'lrn_seed', 'ctx:x', '{}'::jsonb, 'organization', '{}'::jsonb, "
        ":exp, true, :created)"),
        {"o": org, "m": memory_id, "exp": expires_at, "created": created_at})


def test_reset_expires_only_leases_predating_it(conn):
    c, org = conn
    stale = f"tmem_stale_{org[:8]}"
    fresh = f"tmem_fresh_{org[:8]}"
    _seed_lease(c, org, memory_id=stale, created_at=NOW - timedelta(days=1),
               expires_at=NOW + timedelta(days=6))
    _seed_lease(c, org, memory_id=fresh, created_at=NOW + timedelta(minutes=5),
               expires_at=NOW + timedelta(days=6))

    result = reset.apply_organization_reset(c, org_id=org, reason="pivot to devtools ICP", at=NOW)
    # Named for what it actually moves. `adaptive_expired` was the old key and it described the
    # wrong brain entirely: this statement updates `temporary_memories` (Runtime) and never
    # touches `learned_brain_entries` (Adaptive), which holds the HIGHEST preference precedence
    # of the three — so an owner told their pivot had cleared it was told the opposite of true.
    assert result["runtime_memories_expired"] >= 1
    assert "adaptive_expired" not in result
    # Whether an Adaptive entry can carry a TTL at all is ADR-10 and unratified; say so rather
    # than let silence read as "handled".
    assert result["adaptive_ttl_unresolved"] is True

    stale_row = c.execute(text(
        "select active from temporary_memories where org_id=:o and memory_id=:m"),
        {"o": org, "m": stale}).scalar()
    fresh_row = c.execute(text(
        "select active from temporary_memories where org_id=:o and memory_id=:m"),
        {"o": org, "m": fresh}).scalar()
    assert stale_row is False
    assert fresh_row is True


def test_reset_logs_a_reason_and_actor(conn):
    c, org = conn
    result = reset.apply_organization_reset(c, org_id=org, reason="ICP changed", at=NOW,
                                            actor="founder_123")
    row = c.execute(text(
        "select reason, triggered_by, situations_rerun from organization_resets "
        "where reset_id=:id"), {"id": result["reset_id"]}).mappings().first()
    assert row["reason"] == "ICP changed"
    assert row["triggered_by"] == "founder_123"
    assert row["situations_rerun"] is False


def test_mark_situations_rerun_flips_the_flag(conn):
    c, org = conn
    result = reset.apply_organization_reset(c, org_id=org, reason="pivot", at=NOW)
    reset.mark_situations_rerun(c, reset_id=result["reset_id"])
    flag = c.execute(text(
        "select situations_rerun from organization_resets where reset_id=:id"),
        {"id": result["reset_id"]}).scalar()
    assert flag is True


def test_latest_reset_at_returns_the_most_recent(conn):
    c, org = conn
    assert reset.latest_reset_at(c, org_id=org) is None
    reset.apply_organization_reset(c, org_id=org, reason="first pivot", at=NOW)
    reset.apply_organization_reset(c, org_id=org, reason="second pivot",
                                   at=NOW + timedelta(days=1))
    latest = reset.latest_reset_at(c, org_id=org)
    assert latest == NOW + timedelta(days=1)

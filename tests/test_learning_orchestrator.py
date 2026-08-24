"""Layer 6 · Phase 6 — the orchestrator run_learning (live PostgreSQL, rolled back)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.feedback.orchestrator import run_learning, week_key

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

_OUTCOME_COLS = ("outcome_id, org_id, execution_id, decision_hash, capability_id, "
                 "capability_version, play_id, play_version, terminal_state, reason_code, label, "
                 "created_at, closed_at, seconds_to_close, actions_total, actions_completed, "
                 "progress_bp, priority_bp, confidence_bp, band, routing_rule")


def test_week_key_is_iso_year_week():
    assert week_key(NOW) == "2026-W32"


def test_the_heartbeat_drives_the_learning_sweep():
    """Learning is worthless unscheduled. Assert the maintenance heartbeat calls it + reports it."""
    import inspect

    from genios_engine.api import routes
    source = inspect.getsource(routes.run_maintenance_sweep)
    assert "run_learning_sweep" in source, "the heartbeat never runs the learning sweep"
    assert '"learning"' in source, "the sweep result must report what Layer 6 did"


@pytest.fixture()
def conn():
    try:
        from genios_engine.platform.config import get_settings
        from genios_engine.platform.db import get_engine
        from sqlalchemy import text
        url = get_settings().database_url
        if not url:
            pytest.skip("no database configured")
        c = get_engine(url).connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    from sqlalchemy import text
    tx = c.begin()
    if not c.execute(text("select to_regclass('public.learning_runs')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0045 not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _seed_outcomes(c, org, play, label, n):
    from sqlalchemy import text
    for i in range(n):
        c.execute(text(
            f"insert into execution_outcomes ({_OUTCOME_COLS}) values "
            "(:i, :o, :x, 'dh', 'sales', '1.0.0', :p, '1.0.0', 'completed', 'done', :lbl, "
            " :t, :t, 0, 1, 1, 10000, 5000, 7000, 'high', 'rule1_owner')"),
            {"i": f"out_orch_{play}_{i}", "o": org, "x": f"exec_orch_{play}_{i}", "p": play,
             "lbl": label, "t": NOW - timedelta(days=1)})


def test_run_learning_produces_metrics_and_is_weekly_idempotent(conn):
    from sqlalchemy import text
    c, org = conn
    _seed_outcomes(c, org, "followup", "succeeded", 4)

    first = run_learning(c, org_id=org, now=NOW)
    assert "skipped" not in first
    assert first["proposals"] >= 1 and first["published"] >= 1     # outcome metric published
    # a metric row landed
    metrics = c.execute(text("select count(*) from learning_metrics where org_id=:o"),
                        {"o": org}).scalar()
    assert metrics >= 1

    # an append-only evaluation row was written per decision (0046 hardening ledger)
    evals = c.execute(text("select count(*) from learning_object_evaluations "
                           "where org_id=:o and run_id=:r"), {"o": org, "r": first["run_id"]}).scalar()
    assert evals >= 1

    # same week -> the DB claim makes it a no-op
    again = run_learning(c, org_id=org, now=NOW)
    assert again.get("skipped") == "already_ran_this_week"


def test_consent_disabled_skips_after_seeding_policy(conn):
    from sqlalchemy import text
    c, org = conn
    # seed a consent-off policy revision
    c.execute(text(
        "insert into learning_policies (org_id, revision, snapshot, learning_enabled, created_at) "
        "values (:o, 9, '{}', false, :at) on conflict do nothing"), {"o": org, "at": NOW})
    result = run_learning(c, org_id=org, now=NOW)
    assert result.get("skipped") == "consent_disabled"

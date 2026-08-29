"""What the product must do when the database stops accepting writes.

Production sat in Supabase's disk-quota read-only mode for four hours on 2026-08-29. Every write
failed. Nothing said so: `/health` reported ok, the scheduler logged one line and alerted nobody,
and the one billable endpoint kept paying Anthropic for answers it could not record or charge for.

Three behaviours are pinned here. The boot guard lives in `test_migrate_read_only.py`.
"""
from __future__ import annotations

import pytest

from genios_engine.platform import ops_alert, scheduler


# ── the scheduler must not fail quietly ──────────────────────────────────────────────────────
def test_a_crashed_sweep_alerts_and_does_not_only_log(monkeypatch):
    """A timeout alerted and a crash did not — which is backwards.

    A hang is at least visible as a tick that never returns. A crash completes the tick, writes
    one line into a log nobody is tailing, and leaves every dashboard green. A read-only database
    produces a raise, not a hang, so it took the path that stayed silent.
    """
    sent: list[tuple] = []
    monkeypatch.setattr(ops_alert, "notify", lambda ev, **f: sent.append((ev, f)))

    import inspect
    src = inspect.getsource(scheduler)
    assert "scheduler_sweep_crashed" in src, "the crash branch still has no alert"

    # and the alert carries enough to act on without opening the box
    idx = src.index("scheduler_sweep_crashed")
    tail = src[idx:idx + 240]
    assert "error=" in tail and "detail=" in tail


def test_the_crash_branch_still_keeps_the_loop_alive():
    """Alerting must not turn a survivable sweep failure into a dead scheduler."""
    import inspect
    src = inspect.getsource(scheduler)
    crash = src[src.index("except Exception as exc"):].split("if _stop.wait")[0]
    # statements only — the branch's own prose explains that a read-only DB "is a raise, not a
    # hang", and matching that sentence would be the test failing on its own documentation.
    statements = [ln.strip() for ln in crash.splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
    assert not any(s == "raise" or s.startswith("raise ") for s in statements), (
        "the crash branch now re-raises — one bad org would kill every future tick")


# ── the billable surface must not spend money it cannot record ───────────────────────────────
def test_a_billable_query_is_refused_before_the_llm_call_when_writes_are_dead(monkeypatch):
    """The order is the whole fix: refuse first, spend never.

    The old path called Anthropic, failed to log the cost, failed to deduct the credit, failed to
    persist the envelope, and returned a 500. We paid, the tenant was not charged, and the user
    got an error — on every query, for four hours.
    """
    from fastapi import HTTPException

    from genios_engine.api import intelligence_routes as ir

    monkeypatch.setattr("genios_engine.platform.migrate._is_read_only", lambda _e: True)
    monkeypatch.setattr(ops_alert, "notify", lambda *a, **k: None)
    monkeypatch.setattr(ir, "_graph", type("S", (), {"engine": object()})())

    with pytest.raises(HTTPException) as exc:
        ir._refuse_if_unbillable("org_x")

    assert exc.value.status_code == 503
    assert "no credits were charged" in str(exc.value.detail).lower()


def test_a_writable_database_lets_the_query_through(monkeypatch):
    from genios_engine.api import intelligence_routes as ir

    monkeypatch.setattr("genios_engine.platform.migrate._is_read_only", lambda _e: False)
    monkeypatch.setattr(ir, "_graph", type("S", (), {"engine": object()})())
    assert ir._refuse_if_unbillable("org_x") is None


def test_the_refusal_happens_before_run_query_not_after(monkeypatch):
    """Source-level, because the ordering IS the behaviour and a later call site restores the bug."""
    import inspect

    from genios_engine.api import intelligence_routes as ir

    src = inspect.getsource(ir)
    guard = src.index("_refuse_if_unbillable(org_id)")
    spend = src.index("env, res = run_query(")
    assert guard < spend, "the unbillable guard moved after the LLM call"

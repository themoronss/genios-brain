"""Hotfix 19 Oct 2026 — every sweep ends by purging what it made and nothing will read.

Measured on prod: ~1,270 reasoning runs a day at ~91 KB, 98% never referenced by a signal; the heartbeat purge kept
seven days of them (~800 MB) and was not reaching them at all — the database sat at 999 MB of a 500 MB tier. Now
`_run_l2_chain` ends, whatever happened inside it, with a bounded in-process purge: unreferenced runs older than an
hour, and every expertise package but the newest of each situation.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from genios_engine.api import routes
from genios_engine.reason import retention


def test_the_sweep_purge_keeps_an_hour_and_is_bounded(monkeypatch):
    seen = {}

    def purge(engine, *, keep_days, now, max_batches):
        seen.update(engine=engine, keep_days=keep_days, now=now, max_batches=max_batches)
        return {"runs": 7, "context_snapshots": 0, "capability_snapshots": 0}

    monkeypatch.setattr(retention, "purge_expired_reasoning", purge)
    at = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    assert retention.purge_after_sweep("eng", now=at) == {"runs": 7, "context_snapshots": 0,
                                                          "capability_snapshots": 0}
    assert seen == {"engine": "eng", "keep_days": 0, "now": at - timedelta(hours=retention.SWEEP_GRACE_HOURS),
                    "max_batches": 4}
    assert retention.SWEEP_GRACE_HOURS >= 1, "never inside the seconds a run waits for its signal"


def test_a_purge_that_fails_never_fails_the_sweep(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(retention, "purge_expired_reasoning", boom)
    assert retention.purge_after_sweep("eng") == {"error": 1}


def test_the_chain_reclaims_in_a_finally_whatever_happened():
    fn = ast.parse(inspect.getsource(routes._run_l2_chain)).body[0]
    finals = [t for t in ast.walk(fn) if isinstance(t, ast.Try) and t.finalbody]
    assert any("_reclaim_after_sweep" in ast.unparse(t.finalbody[0]) for t in finals)


def test_reclaiming_purges_both_and_keeps_the_newest_package(monkeypatch):
    from genios_engine.packs.compiler import expertise_publisher
    calls = []
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine="eng"))
    monkeypatch.setattr(retention, "purge_after_sweep", lambda engine: calls.append(("runs", engine)))
    monkeypatch.setattr(expertise_publisher, "purge_superseded_expertise_packages",
                        lambda engine, keep: calls.append(("packages", engine, keep)))
    routes._reclaim_after_sweep()
    assert calls == [("runs", "eng"), ("packages", "eng", 1)]


def test_reclaiming_survives_both_purges_failing(monkeypatch):
    from genios_engine.packs.compiler import expertise_publisher

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine="eng"))
    monkeypatch.setattr(retention, "purge_after_sweep", boom)
    monkeypatch.setattr(expertise_publisher, "purge_superseded_expertise_packages", boom)
    routes._reclaim_after_sweep()          # no raise

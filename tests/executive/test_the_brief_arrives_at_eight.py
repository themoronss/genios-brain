"""STEP-15 · the brief arrives at 08:00 — every sweep ends by composing the briefs that are due, and never dies of it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_the_brief_arrives_at_eight.py

`api/routes._compose_due_briefs` (tree `yc2_w27_s15` M44.C4.L-integration.V2.U03; `03` s15-F12: nothing in the engine
ran at a local hour — the heavy tick every six hours from process start, the light one every fifteen minutes). Every
sweep — `run_sync_sweep`, which the 6-hour heavy tick (`run_maintenance_sweep`) and the 15-minute light tick both run,
and `/ingest/all`, after its background reasoning — ends with `executive/morning.compose_due` in a block of its own:
a brief lands within one light tick of the hour, after the morning's mail, and a failure there is counted, never the
beat's.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

ORG = "org_s15_eight"
AT = datetime(2026, 10, 6, 2, 40, tzinfo=timezone.utc)          # 08:10 in Kolkata


@pytest.fixture
def routes(monkeypatch):
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the sweep composes on Postgres")
    from genios_engine.api import routes as R
    from genios_engine.platform.seats import ensure_owner_seat
    engine = R._graph.engine
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', 'eight@example.test', "
                       "'Asia/Kolkata')"), {"o": ORG})
        ensure_owner_seat(c, ORG)
    monkeypatch.setattr(R, "_brief_clock", lambda: AT)
    monkeypatch.setattr(R._connections, "list_active", lambda: [])          # no mailbox to pull: the sweep's tail
    yield R
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _kept(R):
    with R._graph.engine.connect() as c:
        return c.execute(text("select local_date from morning_briefs where org_id = :o"), {"o": ORG}).scalars().all()


def test_a_sweep_ends_by_composing_the_briefs_that_are_due(routes):
    out = routes.run_sync_sweep()
    assert out["briefs"]["composed"] >= 1 and out["briefs"]["failed"] == 0
    assert _kept(routes) == [date(2026, 10, 6)]
    again = routes.run_sync_sweep()                                         # the light tick, fifteen minutes on
    assert again["briefs"]["composed"] == 0 and _kept(routes) == [date(2026, 10, 6)]


def test_a_brief_that_cannot_be_composed_never_kills_the_beat(routes, monkeypatch):
    from genios_engine.executive import morning

    def broken(*_a, **_k):
        raise RuntimeError("the brief's store is down")
    monkeypatch.setattr(morning, "compose_due", broken)
    out = routes.run_sync_sweep()
    assert out["briefs"] == {"error": "RuntimeError"} and "connections" in out


def test_both_ticks_and_ingest_all_end_with_the_briefs(routes, monkeypatch):
    from genios_engine.platform import scheduler
    seen = []
    monkeypatch.setattr(routes, "run_sync_sweep", lambda **kw: seen.append(("sync", kw)) or {"briefs": {}})
    scheduler._light_tick()
    assert seen == [("sync", {"chain_only_on_new_data": True})]
    import inspect
    assert "run_sync_sweep(" in inspect.getsource(routes.run_maintenance_sweep)   # the heavy tick runs the same sweep

    class _Tasks:
        def __init__(self):
            self.tasks = []

        def add_task(self, fn, *args, **kw):
            self.tasks.append(fn)
    tasks = _Tasks()
    monkeypatch.setattr(routes, "_connections", type("C", (), {"list_active": staticmethod(lambda: [])})())
    routes.ingest_all(background_tasks=tasks, mode="incremental", limit=1, auto_l2=True, _internal=None)
    assert tasks.tasks and tasks.tasks[-1] is routes._compose_due_briefs        # after every org's reasoning

"""STEP-05 · the progress count asks exactly the drain's question.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_the_pending_count_is_the_pull.py -q

Tree `yc2_w27_s05 · M23.C2.L-data.V1.U02`. `api/routes._pending_count` — the onboarding progress
total — counted every emitted event not yet done, while `context/runner._pull` took only events with a
live signal: it said "waiting" for mail the drain would never take, and nothing about archived mail the
drain now reads. Now both read `context/runner.PENDING_FROM`, one spelling, so they move together.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.context import test_every_kept_event_is_pulled as seed

pytestmark = pytest.mark.pg
ORG = seed.ORG


@pytest.fixture
def store(pg_store):
    seed._reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'founder.pull@gmail.com')"),
                  {"o": ORG})
    yield pg_store
    seed._reset(pg_store)


def test_the_count_is_what_the_drain_would_take(store, monkeypatch):
    from genios_engine.api import routes
    from genios_engine.context import runner

    monkeypatch.setattr(routes, "_graph", store)
    with store.engine.begin() as c:
        seed._event(c, "p_signal"); seed._extraction(c, "p_signal", "xp_signal")
        seed._signal(c, "p_signal", "xp_signal")
        seed._event(c, "p_below"); seed._extraction(c, "p_below", "xp_below")
        seed._event(c, "p_unread")                                   # nothing to read: not pending
        seed._event(c, "p_unread_too")                               # (the old count said 2 more)
        seed._event(c, "p_archived", outcome="archived")
        seed._event(c, "p_parked", outcome="parked"); seed._extraction(c, "p_parked", "xp_parked")
    pulled = {r.event_id for r in runner._pull(store, ORG, 1000)}
    assert pulled == {"p_signal", "p_below", "p_archived"}
    assert routes._pending_count(ORG) == len(pulled)

    with store.engine.begin() as c:
        c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                       "values (:o, 'p_below', 'done', 1)"), {"o": ORG})
    assert routes._pending_count(ORG) == len(runner._pull(store, ORG, 1000)) == 2


def test_both_read_one_spelling():
    """By the source: the count is `select count(*)` over the drain's own FROM and WHERE."""
    import inspect

    from genios_engine.api import routes

    src = inspect.getsource(routes._pending_count)
    assert "PENDING_FROM" in src and "pending_params" in src
    assert "outcome='emitted'" not in src, "a second spelling of the drain's question is back"

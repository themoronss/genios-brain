"""STEP-12 · situations are minted in the order their correlations were opened — never in heap order.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_situations_are_minted_in_the_order_they_opened.py -q

Tree `yc2_w27_s12` M32.C5.L-data.V1.U06, `03` F172. `context/situations.refresh_situations` read the
tenant's correlations with no ORDER BY and gave each new situation the next id. On a fresh database the
heap returns rows in the order they were written, so it looked deterministic; once deleted tenants have
left holes, or a correlation's row has been rewritten in place, it does not — and the golden set mints its
ids from a per-case sequence, so a long run gave F54's three files other situation ids than its recording,
and every review citing them was refused. Here three correlations are opened in one order and their rows
are then rewritten so the heap holds them in another; the situations must still be minted in the order
the correlations were opened.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import situations

pytestmark = pytest.mark.pg

ORG = "org_s12_situation_order"


@pytest.fixture
def opened(pg_store):
    """Three files opened one after another — Lumen first, then Quill, then Ash — each by one mail,
    the mails dated the other way round (a backfill reads the newest first), so neither the dates nor
    the heap is the order they opened."""
    from tests.context.workstream_world import T0, process, reset, tenant
    tenant(pg_store, ORG)
    for n, (event_id, sender) in enumerate((("evt_lumen", "kim@lumen.test"),
                                            ("evt_quill", "ola@quill.test"),
                                            ("evt_ash", "ravi@ash.test"))):
        process(pg_store, ORG, event_id=event_id, sender=sender, thread=f"t_{n}",
                at=T0 - timedelta(hours=n))
    with pg_store.engine.begin() as c:
        rows = c.execute(text(
            "select k.correlation_id, m.event_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id "
            "       and m.correlation_id = k.correlation_id where k.org_id = :o"), {"o": ORG}).all()
        by_event = {r.event_id: r.correlation_id for r in rows}
        order = [by_event["evt_lumen"], by_event["evt_quill"], by_event["evt_ash"]]
        # The order they were opened, stated — one transaction each in production; here, explicitly.
        for n, correlation_id in enumerate(order):
            c.execute(text("update context_correlations set created_at = :at "
                           " where org_id = :o and correlation_id = :c"),
                      {"o": ORG, "c": correlation_id, "at": T0 + timedelta(minutes=n)})
        # ⛔ AND THE HEAP SHUFFLED: each row rewritten in the reverse order, moving an indexed column
        # (a second on its last event), so no index keeps the old order (no HOT chain). On a fresh
        # database a read with no order then returns Ash, Quill, Lumen — the reverse of how they
        # opened, as a long run's freed space does. On a database other tests have churned, where the
        # rewritten rows land is the free space's business: the order the SQL declares is held below
        # on its own, so a shuffle that did not take cannot leave the order unproven.
        for correlation_id in reversed(order):
            c.execute(text("update context_correlations "
                           "   set last_event_at = last_event_at + interval '1 second' "
                           " where org_id = :o and correlation_id = :c"),
                      {"o": ORG, "c": correlation_id})
        c.execute(text("delete from context_situations where org_id = :o"), {"o": ORG})
    try:
        yield pg_store, order
    finally:
        reset(pg_store, ORG)


def test_each_new_situation_takes_the_next_id_in_the_order_its_correlation_opened(opened, monkeypatch):
    store, order = opened
    minted: list[str] = []

    def _next(prefix: str) -> str:
        minted.append(prefix)
        return f"{prefix}_{len(minted):03d}"
    monkeypatch.setattr(situations, "new_id", _next)
    from tests.context.workstream_world import T0
    situations.refresh_situations(store, ORG, eval_time=T0 + timedelta(days=1))
    with store.engine.connect() as c:
        ids = dict(c.execute(text("select correlation_id, situation_id from context_situations "
                                  " where org_id = :o"), {"o": ORG}).all())
    assert [ids[c] for c in order] == ["sit_001", "sit_002", "sit_003"], ids


def test_the_correlations_are_read_in_the_order_they_opened(opened, monkeypatch):
    """The order the ids are given in is the order the read DECLARES — opened first, ties by id —
    whatever the heap holds."""
    store, _order = opened
    reads: list[str] = []
    original = situations._bulk

    def _recorded(conn, sql, params):
        reads.append(" ".join(sql.split()).lower())
        return original(conn, sql, params)
    monkeypatch.setattr(situations, "_bulk", _recorded)
    from tests.context.workstream_world import T0
    situations.refresh_situations(store, ORG, eval_time=T0 + timedelta(days=1))
    [read] = [r for r in reads if r.startswith("select correlation_id, anchor_node_id")]
    assert read.endswith("from context_correlations where org_id = :o "
                         "order by created_at, correlation_id"), read

"""RS-5 — no per-person objective reached ranking; now one reorders a viewer's own queue.

    pytest tests/deliver/test_an_objective_reorders_and_scores_nothing.py -q

`user_models.priorities_jsonb` was written and read only by its own CRUD file. Two store
managers on the same morning — one three days from a launch, the other mid-audit — got a queue
ordered by the identical formula over the identical tenant-wide set.

The design is the whole point: a STABLE PARTITION at the per-viewer queue read. Cards in the
objective's domain first, then the rest, each half in its existing utility order. No score
moves, nothing is removed, two viewers still see identical facts — a preference changes the
order of an explanation and never the evidence in it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver.store import CardStore

pytestmark = pytest.mark.unit

ORG = "org1"


def rows(*domains):
    return [{"card_id": f"c{i}", "domain": d, "score": 100 - i} for i, d in enumerate(domains)]


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table org_seats (org_id text, seat_id text, email text, "
                       "active boolean)"))
        c.execute(text("create table seat_objectives (org_id text, seat_key text, "
                       "domain text, owner text, note text, added_at timestamp, "
                       "valid_until timestamp)"))
        c.execute(text("insert into org_seats values (:o,'seat-a','anisha@acme.test',1)"),
                  {"o": ORG})
        yield c


def test_the_objective_domain_leads_and_nothing_else_moves(conn):
    conn.execute(text("insert into seat_objectives values (:o,'anisha@acme.test','support',"
                      "'owner','launch week', current_timestamp, null)"), {"o": ORG})

    got = CardStore._objective_order(conn, ORG, "seat-a",
                                            rows("sales", "support", "admin", "support"))

    assert [r["card_id"] for r in got] == ["c1", "c3", "c0", "c2"]
    assert [r["score"] for r in got] == [99, 97, 100, 98], "each half keeps its utility order"


def test_nothing_is_hidden(conn):
    conn.execute(text("insert into seat_objectives values (:o,'anisha@acme.test','support',"
                      "'owner','', current_timestamp, null)"), {"o": ORG})
    before = rows("sales", "support", "admin")

    got = CardStore._objective_order(conn, ORG, "seat-a", before)

    assert sorted(r["card_id"] for r in got) == sorted(r["card_id"] for r in before)


def test_no_objective_leaves_the_order_untouched(conn):
    before = rows("sales", "support", "admin")

    assert CardStore._objective_order(conn, ORG, "seat-a", before) == before


def test_an_expired_objective_no_longer_applies(conn):
    conn.execute(text("insert into seat_objectives values (:o,'anisha@acme.test','support',"
                      "'owner','', '2026-01-01', '2026-02-01')"), {"o": ORG})
    before = rows("sales", "support")

    assert CardStore._objective_order(conn, ORG, "seat-a", before) == before


def test_an_unnamed_viewer_is_never_reordered(conn):
    """An admin reading the org queue and an org-level key have no person to hold an objective."""
    before = rows("sales", "support")

    assert CardStore._objective_order(conn, ORG, None, before) == before


def test_an_unreadable_preference_table_fails_to_the_existing_order():
    engine = create_engine("sqlite://")
    with engine.begin() as c:            # no tables at all
        before = rows("sales", "support")
        assert CardStore._objective_order(c, ORG, "seat-a", before) == before


def test_the_queue_read_now_carries_the_domain_it_partitions_on():
    import inspect

    src = inspect.getsource(CardStore.queue)

    assert "k.assignee, k.domain, k.urgency_band" in src
    assert "rows = self._objective_order(c, org_id, assignee, rows)" in src

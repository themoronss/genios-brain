"""`03` F97 · a brief read through a connection sees that transaction — and is never cached from it.

    GENIOS_TEST_DATABASE_URL=… pytest tests/platform/test_a_brief_read_in_a_transaction_sees_it.py -q

`yc2_w27_s18` M49.C2.L-logic.V0.U04 (platform).

⛔ WHAT WAS WRONG. `platform/company_brief.current` promised *"A connection is accepted too, and read
through without the cache — a caller inside a transaction sees its own writes"* and did neither:
`_engine(conn)` took `conn.engine`, opened a connection of its own (which cannot see the caller's
uncommitted lines), served a cached brief first, and cached what that other connection saw — so an
empty brief read mid-transaction was served for a minute after the commit. Latent: every production
caller passes an engine or a store. Measured red first on Postgres.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import company_brief as CB
from genios_engine.platform import company_brief_store as BS

pytestmark = pytest.mark.pg

ORG = "org_s18_brief_in_a_transaction"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(pg_store):
    _reset(pg_store.engine)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'Brief')"), {"o": ORG})
    yield pg_store.engine
    _reset(pg_store.engine)


def _reset(engine) -> None:
    with engine.begin() as c:
        c.execute(text("delete from company_brief_lines where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    CB.invalidate(ORG)


def _add(conn) -> None:
    BS.add(conn, org_id=ORG, section="goals", words="raise the pre-seed round",
           decided_by="founder", at=AT)


def test_a_caller_inside_a_transaction_sees_its_own_line(engine):
    with engine.begin() as c:
        _add(c)
        assert CB.current(c, ORG).version, "the caller's own accepted line, not yet committed"


def test_a_read_through_a_connection_is_never_served_from_the_cache(engine):
    assert not CB.current(engine, ORG).version                      # cached: no brief yet
    with engine.begin() as c:
        _add(c)
        assert CB.current(c, ORG).version, "the connection's read was served the cached empty brief"


def test_a_read_through_a_connection_never_fills_the_cache(engine):
    c = engine.connect()
    tx = c.begin()
    try:
        _add(c)
        CB.current(c, ORG)
    finally:
        tx.rollback()
        c.close()
    # The line was rolled back. Had the transaction's read been cached, the engine would be served
    # a brief that never committed.
    assert not CB.current(engine, ORG).version


def test_an_engine_read_is_still_cached(engine):
    """The negative half: the per-process copy is unchanged for an engine or a store — a second read
    inside the TTL is the same object (the store's own writes invalidate it, by design)."""
    first = CB.current(engine, ORG)
    assert CB.current(engine, ORG) is first, "an engine read inside the TTL is the cached copy"

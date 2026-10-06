"""STEP-04 · U06 — the send-hour histogram reads mail sent by any of us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_timezone_reads_what_we_sent.py -q

`deliver/timezone_infer.outbound_timestamps` is the evidence `orgs.timezone` is inferred from:
people send mail while they are awake. It decided whose mail that was with its own copy of the
tenant SQL — every seat, active or not, and `orgs.email` — so a founder who writes from his
connected mailbox or from the address he declared his own (`ceo@thegenios.com`,
`org_self_identities`, migration 0193) had no outbound mail at all, and his quiet hours stayed in
UTC; while a colleague who left still set the org's working day.

It asks `platform/self_identity.identity_for` now (tree `yc2_w27_s04/M22.C2.L-logic.V2.U06`).
"""
from __future__ import annotations

import ast
import inspect
import itertools
import json
import os
import textwrap
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver import timezone_infer

pytestmark = pytest.mark.pg
ORG = "s04_timezone_us"
#: `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
OWNER = "Founder.S04Tz@gmail.com"
CONNECTION = "conn_s04_timezone_us"
_EVENT_IDS = itertools.count()


@pytest.fixture
def conn():
    """A real-Postgres transaction, rolled back: a founder, his connected mailbox, the address he
    declared, and a seat that left."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    c = engine.connect()
    tx = c.begin()
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
              {"o": ORG, "e": OWNER})
    c.execute(text("insert into connections (connection_id, org_id, external_account_id) "
                   "values (:c, :o, 'Founder.S04Tz.Mailbox@gmail.com')"),
              {"c": CONNECTION, "o": ORG})
    c.execute(text("insert into org_seats (org_id, seat_id, email, active) "
                   "values (:o, 'seat_s04_tz_gone', 'left.s04tz@oldco.test', false)"), {"o": ORG})
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                   "values (:o, 'address', 'ceo@thegenios.com', 'test')"), {"o": ORG})
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _sent(c, sender: str, at: datetime) -> datetime:
    """One message on the tenant's connection, written by `sender` at `at`."""
    event_id = f"evt_s04_tz_{next(_EVENT_IDS)}"
    c.execute(text("insert into source_events (event_id, org_id, connection_id, source, "
                   "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                   "(:e, :o, :c, 'gmail', 'message', :e, :e, cast(:a as jsonb), :t)"),
              {"e": event_id, "o": ORG, "c": CONNECTION, "a": json.dumps({"email": sender}),
               "t": at})
    return at


def _at(day: int) -> datetime:
    return datetime(2026, 9, day, 4, 30, tzinfo=timezone.utc)


def test_mail_from_every_address_of_ours_is_counted(conn):
    ours = {_sent(conn, OWNER, _at(1)),                                   # orgs.email, as written
            _sent(conn, "founder.s04tz.mailbox@gmail.com", _at(2)),       # the connected account
            _sent(conn, "ceo@thegenios.com", _at(3))}                     # the declared address
    assert set(timezone_infer.outbound_timestamps(conn, ORG)) == ours


def test_mail_from_the_other_side_is_not_ours(conn):
    _sent(conn, "priya@acme.test", _at(4))
    assert timezone_infer.outbound_timestamps(conn, ORG) == []


def test_a_seat_that_left_no_longer_sets_our_working_day(conn):
    _sent(conn, "left.s04tz@oldco.test", _at(5))
    assert timezone_infer.outbound_timestamps(conn, ORG) == []


def test_a_founder_who_writes_from_his_declared_address_gets_his_zone(conn):
    """End to end: an Indian founder whose outbound mail all leaves from `ceo@thegenios.com`."""
    base = datetime(2026, 3, 2, tzinfo=timezone.utc)
    for day in range(15):
        for local_hour in (9, 11, 14, 16, 18, 21):
            _sent(conn, "ceo@thegenios.com", base + timedelta(days=day, hours=local_hour - 5.5))
    result = timezone_infer.infer_and_store(conn, ORG)
    assert result["timezone"] == "Asia/Kolkata", result


def test_the_histogram_asks_the_one_answer():
    """`outbound_timestamps` reads `identity_for`; the seats/orgs union is not re-written here."""
    fn = ast.parse(textwrap.dedent(inspect.getsource(timezone_infer.outbound_timestamps))).body[0]
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "identity_for" in called, "outbound_timestamps does not ask platform/self_identity"
    # The docstring is prose about the query, not a statement it runs — never measured as SQL.
    first = fn.body[0]
    docstring = first.value if (isinstance(first, ast.Expr)
                                and isinstance(first.value, ast.Constant)) else None
    sql = [n.value for n in ast.walk(fn)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and n is not docstring]
    assert not [s for s in sql if "org_seats" in s], (
        "outbound_timestamps still carries its own copy of the tenant identity SQL")

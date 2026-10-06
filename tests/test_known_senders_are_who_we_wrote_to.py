"""STEP-04 · U07 — a known sender is somebody ANY of us wrote to.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_known_senders_are_who_we_wrote_to.py -q

W-01 (`whitelist()`: do not destructively drop this) protects mail from a known counterparty, and
`api/routes.known_counterparty_keys` builds that set from two halves. The sent-folder half,
`KNOWN_FROM_SENT_SQL`, counted the recipients of mail whose author was a SEAT — any seat, active or
not — so everyone the founder wrote to from `orgs.email`, from his connected mailbox, or from the
address he declared his own (`ceo@thegenios.com`, `org_self_identities`, migration 0193) stayed a
stranger to the noise gate, while a colleague who left still vouched for the people she wrote to.

It reads the one answer now — `platform/self_identity.identity_for(...).addresses`, bound as
`= any(:ours)` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U07`). The definition does not widen: an
address is known only as a RECIPIENT of mail one of us SENT.
"""
from __future__ import annotations

import ast
import inspect
import itertools
import json
import os
import textwrap
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.api import routes

pytestmark = pytest.mark.pg
ORG = "s04_known_senders"
#: `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
OWNER = "Founder.S04Known@gmail.com"
CONNECTION = "conn_s04_known_senders"
_EVENT_IDS = itertools.count()


@pytest.fixture
def conn():
    """A real-Postgres transaction, rolled back: every source of who we are, and a seat that left."""
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
                   "values (:c, :o, 'Founder.S04Known.Mailbox@gmail.com')"),
              {"c": CONNECTION, "o": ORG})
    c.execute(text("insert into org_seats (org_id, seat_id, email, active) values "
                   "(:o, 'seat_s04_known_harsh', 'harsh@thegenios.com', true), "
                   "(:o, 'seat_s04_known_gone', 'left.s04known@oldco.test', false)"), {"o": ORG})
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                   "values (:o, 'address', 'ceo@thegenios.com', 'test')"), {"o": ORG})
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _mail(c, sender: str, recipients: list[str]) -> None:
    """One captured message: `sender` wrote it, to `recipients`."""
    event_id = f"evt_s04_known_{next(_EVENT_IDS)}"
    c.execute(text("insert into source_events (event_id, org_id, connection_id, source, "
                   "object_type, source_object_id, dedup_key, actor, occurred_at, recipients) "
                   "values (:e, :o, :c, 'gmail', 'message', :e, :e, cast(:a as jsonb), :t, "
                   "cast(:r as text[]))"),
              {"e": event_id, "o": ORG, "c": CONNECTION, "a": json.dumps({"email": sender}),
               "t": datetime(2026, 9, 1, 10, tzinfo=timezone.utc), "r": recipients})


@pytest.mark.parametrize("sender, recipient", [
    (OWNER, "a.s04@client.test"),                                  # orgs.email, as written
    ("founder.s04known.mailbox@gmail.com", "b.s04@client.test"),   # the connected account
    ("ceo@thegenios.com", "c.s04@client.test"),                    # the declared address
    ("harsh@thegenios.com", "d.s04@client.test"),                  # an active seat
])
def test_whoever_any_of_us_wrote_to_is_known(conn, sender, recipient):
    _mail(conn, sender.lower(), [recipient])
    assert recipient in routes.known_counterparty_keys(conn, ORG), (
        f"{sender} is ours and wrote to {recipient}, who is still a stranger to the noise gate")


def test_a_seat_that_left_no_longer_vouches_for_anyone(conn):
    _mail(conn, "left.s04known@oldco.test", ["e.s04@client.test"])
    assert "e.s04@client.test" not in routes.known_counterparty_keys(conn, ORG)


def test_a_stranger_who_writes_in_is_still_a_stranger(conn):
    """NOT A WIDENING: mail that reached us makes nobody known — not its sender, not its other
    recipients."""
    _mail(conn, "cold.caller@spam.test", [OWNER.lower(), "f.s04@client.test"])
    keys = routes.known_counterparty_keys(conn, ORG)
    assert "cold.caller@spam.test" not in keys and "f.s04@client.test" not in keys


def test_the_sent_half_asks_the_one_answer():
    """The sender check reads `identity_for`; no seats query is written into the statement."""
    fn = ast.parse(textwrap.dedent(inspect.getsource(routes.known_counterparty_keys))).body[0]
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "identity_for" in called, "known_counterparty_keys does not ask platform/self_identity"
    assert "org_seats" not in routes.KNOWN_FROM_SENT_SQL, (
        "the sent-folder half still carries its own copy of the tenant identity SQL")
    assert "= any(:ours)" in routes.KNOWN_FROM_SENT_SQL

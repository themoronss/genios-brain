"""STEP-04 · U08 — the health check counts who ANY of us wrote to, exactly as W-01 does.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_known_senders.py -q

`scripts/pipeline_health.check_the_known_sender_set_is_not_empty` fails a deploy when the tenant
knows nobody it has written to — the set W-01 (`api/routes.known_counterparty_keys`) protects mail
with. It carried its own copy of the sent-folder query, with its own idea of "us": every seat,
active or not. So it went red on a founder who writes from `orgs.email`, his connected mailbox or
the address he declared (`ceo@thegenios.com`), green on a seat that left, and counted a blank
recipient W-01 drops — the check and the thing it checks could disagree.

It reads the same identity now — `platform/self_identity.identity_for(...).addresses`, in W-01's
own statement shape (tree `yc2_w27_s04/M22.C2.L-logic.V2.U08`).
"""
from __future__ import annotations

import ast
import importlib
import inspect
import itertools
import json
import os
import re
import textwrap
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "s04_health_known"
#: `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
OWNER = "Founder.S04Health@gmail.com"
CONNECTION = "conn_s04_health_known"
_EVENT_IDS = itertools.count()


def _health():
    return importlib.import_module("scripts.pipeline_health")


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
                   "values (:c, :o, 'Founder.S04Health.Mailbox@gmail.com')"),
              {"c": CONNECTION, "o": ORG})
    c.execute(text("insert into org_seats (org_id, seat_id, email, active) "
                   "values (:o, 'seat_s04_health_gone', 'left.s04health@oldco.test', false)"),
              {"o": ORG})
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                   "values (:o, 'address', 'ceo@thegenios.com', 'test')"), {"o": ORG})
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _mail(c, sender: str, recipients: list[str]) -> None:
    event_id = f"evt_s04_health_{next(_EVENT_IDS)}"
    c.execute(text("insert into source_events (event_id, org_id, connection_id, source, "
                   "object_type, source_object_id, dedup_key, actor, occurred_at, recipients) "
                   "values (:e, :o, :c, 'gmail', 'message', :e, :e, cast(:a as jsonb), :t, "
                   "cast(:r as text[]))"),
              {"e": event_id, "o": ORG, "c": CONNECTION, "a": json.dumps({"email": sender}),
               "t": datetime(2026, 9, 1, 10, tzinfo=timezone.utc), "r": recipients})


def _known(check) -> int:
    match = re.match(r"(\d+) known counterparties from \d+ outbound events", check.measured)
    assert match, check.measured
    return int(match.group(1))


@pytest.mark.parametrize("sender", [OWNER.lower(), "founder.s04health.mailbox@gmail.com",
                                    "ceo@thegenios.com"])
def test_a_founder_who_writes_from_any_address_of_ours_knows_people(conn, sender):
    _mail(conn, sender, ["a.s04@client.test", "b.s04@client.test"])
    check = _health().check_the_known_sender_set_is_not_empty(conn, ORG)
    assert check.ok and _known(check) == 2, check.measured


def test_mail_a_seat_that_left_sent_makes_nobody_known(conn):
    _mail(conn, "left.s04health@oldco.test", ["c.s04@client.test"])
    check = _health().check_the_known_sender_set_is_not_empty(conn, ORG)
    assert _known(check) == 0 and not check.ok, check.measured


def test_the_check_and_w01_cannot_disagree(conn):
    """The same people, counted the same way: a blank recipient is nobody, in both."""
    from genios_engine.api.routes import known_counterparty_keys

    _mail(conn, "ceo@thegenios.com", ["d.s04@client.test", " ", ""])
    _mail(conn, OWNER.lower(), ["D.S04@client.test", "e.s04@client.test"])
    _mail(conn, "cold.caller@spam.test", [OWNER.lower(), "f.s04@client.test"])
    check = _health().check_the_known_sender_set_is_not_empty(conn, ORG)
    assert _known(check) == len(known_counterparty_keys(conn, ORG)) == 2, check.measured


def test_the_check_asks_the_one_answer():
    """The check reads `identity_for` and runs W-01's statement shape; no seats query of its own."""
    fn = ast.parse(textwrap.dedent(
        inspect.getsource(_health().check_the_known_sender_set_is_not_empty))).body[0]
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "identity_for" in called, "the check does not ask platform/self_identity"
    # The statements handed to `_scalar`, never the docstring or the `fix=` prose.
    statements = [arg.value for n in ast.walk(fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "_scalar"
                  for arg in n.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
    assert statements, "no statement reached `_scalar` — re-point this test"
    assert not [s for s in statements if "org_seats" in s], (
        "the check still carries its own copy of the tenant identity SQL")
    assert [s for s in statements if "= any(:ours)" in s], "the check does not bind our addresses"

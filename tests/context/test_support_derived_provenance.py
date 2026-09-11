"""Actual support fact SQL retains the events carried by the reading."""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from .test_derived_provenance import provenance_db  # shared real SQLite fixture
from genios_engine.context.derived_provenance import load_event_receipts
from genios_engine.context.support_situations import (
    Desk, Message, ResponsePolicy, _write_fact, read_first_response,
)

NOW = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)


def _fact_schema(conn):
    conn.execute(text("""create table graph_facts (
        fact_version_id text primary key, fact_id text, org_id text, subject_node_id text,
        field text, value text, value_type text, status text, authority_rank int,
        confidence real, occurred_at timestamp, valid_from timestamp, visibility_scope text,
        derivation_type text, trace_id text, schema_version text, source_authority text,
        provenance_refs text)"""))


def test_a_support_fact_write_persists_both_source_refs_with_its_fact_version(provenance_db):
    conn = provenance_db
    _fact_schema(conn)
    receipts = load_event_receipts(conn, org_id="o", event_ids=("e1", "e2"))
    for _ in range(2):
        _write_fact(conn, org_id="o", node_id="derived", field_name="response.channel",
                    value="email", value_type="enum", now=NOW, key="stable",
                    event_receipts=receipts)
    row = conn.execute(text("select * from graph_facts")).mappings().one()
    assert json.loads(row["value"]) == "email"
    refs = conn.execute(text("select event_id, source, fact_version_id from graph_source_refs where fact_version_id=:v order by event_id"),
                        {"v": row["fact_version_id"]}).all()
    assert refs == [("e1", "gmail", row["fact_version_id"]), ("e2", "gcal", row["fact_version_id"])]
    assert set(json.loads(row["provenance_refs"])) >= {"e1", "e2"}


def test_the_first_response_reading_carries_the_messages_it_actually_read():
    opened = NOW - timedelta(days=7)
    messages = tuple(Message(event_id=e, thread_id="t", at=opened + timedelta(hours=i),
        sender="customer@example.com", internal=False, recipients=("owner@example.com",),
        head="Please send the security review.") for i, e in enumerate(("e1", "e2")))
    desk = Desk(org_id="o", now=NOW, internal=frozenset({"owner@example.com"}),
        internal_domains=frozenset({"example.com"}), messages=messages,
        thread_first={"t": opened}, thread_node={"t": "thread-node"},
        policy=ResponsePolicy())
    findings = read_first_response(desk)
    assert len(findings) == 1
    assert findings[0].event_ids == ("e1", "e2")


def test_every_message_backed_support_reading_retains_its_known_event_ids():
    from tests.test_support_situations import _every_finding
    from genios_engine.context.support_situations import ANCHOR_BACKLOG_ITEM, ANCHOR_MAILBOX

    findings = _every_finding()
    assert len({finding.anchor for finding in findings}) == 7
    for finding in findings:
        if finding.anchor in {ANCHOR_BACKLOG_ITEM, ANCHOR_MAILBOX}:
            # These two original fixtures contain only ledger rows, no source messages.
            assert finding.event_ids == ()
        else:
            assert finding.event_ids, finding.anchor
            assert all(event.startswith("ev_") for event in finding.event_ids)


def test_backlog_and_mailbox_readings_keep_available_message_receipts():
    from dataclasses import replace
    from tests.test_support_situations import _desk, _load_desk, _loop, _msg, _ago, US
    from genios_engine.context.support_situations import read_backlog_items, read_mailbox_load

    msg = _msg("t1", _ago(40), US, internal=True, head="We are reviewing the request.")
    desk = _desk(messages=(msg,), loops=(_loop("l1", "t1", days_open=30),),
        thread_node={"t1": "n_t1"}, thread_facts={"n_t1": {"thread.ball_in_court": "us"}})
    assert read_backlog_items(desk)[0].event_ids == (msg.event_id,)
    mailbox = replace(_load_desk([_loop(f"l{n}", "t1", days_open=40) for n in range(3)]),
                      messages=(msg,))
    assert read_mailbox_load(mailbox)[0].event_ids == (msg.event_id,)

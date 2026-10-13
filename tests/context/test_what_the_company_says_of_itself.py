"""STEP-13b · what the company says of itself, in its own mail — the record every file may read (`06` D63).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_what_the_company_says_of_itself.py

Tree `yc2_w27_s13b · M37.C2.L-data.V0.U04`. F52: Ridgeline's Gautam set a bar in April — "re-engage once
you have ten paying customers" — and on 12 Sep the founder wrote to Vertex Angels, on ANOTHER file, "we
crossed 12 paying customers this month". Ridgeline's dossier could not see it, so the file asked the
founder a question his own mail had answered (`06` D63: "keep the question for now … that reading is
STEP-13b's"). `context/company_record` reads, once a sweep, every outbound mail of ours that is KEPT (an
archive's words are never read), and keeps the sentences that name us — the company by its name, or "we"
— beside a number or a milestone: newest first, bounded, every cut counted. A date or a time is no
number about us, and a question is no statement.

The selection is pure (`record_of`) and tested without a database; `read_company_record` is the one read.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context import company_record as R

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
UPDATE = ("Hi Nandini,\n\nA quick update: we crossed 12 paying customers this month, and onboarding is "
          "down to two days.\n\nArjun")


def _row(event_id: str, words: str | None, *, days_ago: float = 1, thread: str = "t1",
         mailbox: str = "con_gmail") -> dict:
    return {"event_id": event_id, "occurred_at": NOW - timedelta(days=days_ago), "words": words,
            "thread": thread, "mailbox": mailbox}


def _record(rows, **kw) -> R.CompanyRecord:
    return R.record_of(rows, org_id="org_x", as_of=NOW, names=kw.pop("names", ("Nimbus Labs",)), **kw)


# ── what is a statement about us ───────────────────────────────────────────────────────────────

def test_f52_the_update_to_vertex_is_a_line_of_the_record():
    record = _record([_row("evt_update", UPDATE, days_ago=8)])
    assert [line.event_id for line in record.lines] == ["evt_update"]
    line = record.lines[0]
    assert "we crossed 12 paying customers this month" in line.said
    assert "Hi Nandini" not in line.said and "Arjun" not in line.said.replace("Arjun Rao", ""), (
        "only the statement is kept — the greeting and the signature are no record")
    assert line.at == NOW - timedelta(days=8)


@pytest.mark.parametrize("sentence", [
    "Nimbus Labs crossed 12 paying customers in August.",        # the company by its name
    "We have 40 pilots running across three hospitals.",         # we, beside a number
    "Our MRR is now 4,20,000 a month.",                          # our, beside a number
    "We launched the self-serve tier last week.",                # we, beside a milestone
    "We've signed our first enterprise customer.",
    "We're now at 9 paying customers.",
])
def test_a_sentence_naming_us_beside_a_number_or_a_milestone_is_kept(sentence):
    assert _record([_row("e1", f"Hello there. {sentence} Best, Arjun")]).lines[0].said == sentence


@pytest.mark.parametrize("sentence", [
    "We will send the deck tomorrow.",                            # us, but no number and no milestone
    "Can we meet on 14 Oct at 3pm?",                             # a question, and a date
    "Have we crossed 10 paying customers yet?",                  # a question asks; it states nothing
    "We are free on 14 Oct.",                                    # a date is no number about us
    "We spoke at 10:30 yesterday.",                              # a time
    "We met on 2026-09-01 in Bengaluru.",                        # an ISO date
    "We can do Thursday the 18th.",                              # an ordinal day
    "They crossed 12 paying customers.",                         # a number, but not about us
    "We'll hit 20 customers by December.",                       # a projection is not a record
    "Weekly numbers attached.",                                  # "we" inside a word is no we
])
def test_anything_else_is_not_a_statement_about_us(sentence):
    assert _record([_row("e1", sentence)]).lines == ()


def test_the_company_s_name_is_a_whole_name_matched_whatever_its_case():
    assert _record([_row("e1", "NIMBUS LABS crossed 12 paying customers.")]).lines
    assert not _record([_row("e1", "Nimbusly crossed 12 paying customers.")]).lines
    assert _record([_row("e1", "Nimbus Labs crossed 12 paying customers.")], names=()).lines == (), (
        "with no company name only `we` names us")


def test_a_mail_with_no_words_is_no_record():
    assert _record([_row("e1", None), _row("e2", "   ")]).lines == ()


def test_every_statement_of_a_mail_is_kept_in_its_order():
    words = "We crossed 12 customers. Thanks for asking. We hired our first engineer."
    assert _record([_row("e1", words)]).lines[0].said == (
        "We crossed 12 customers. We hired our first engineer.")


def test_a_long_statement_is_cut_on_a_word_and_the_cut_counted():
    long = "We crossed 12 paying customers, " + "abcdefghi " * 100 + "more."
    assert long[R.SAID_CHARS - 1] != " " and long[R.SAID_CHARS] != " ", "the limit falls inside a word"
    line = _record([_row("e1", long)]).lines[0]
    assert len(line.said) <= R.SAID_CHARS and not line.said.endswith(" ")
    assert line.said.split()[-1] == "abcdefghi", "never cut inside a word"
    assert line.said_cut == len(long) - len(line.said)
    assert long.startswith(line.said)
    short = "We crossed 12 paying customers."
    assert _record([_row("e2", short)]).lines[0].said_cut == 0


# ── bounded, newest first, counted ─────────────────────────────────────────────────────────────

def test_newest_first_bounded_and_the_rest_counted():
    rows = [_row(f"e{i:02d}", f"We crossed {i + 3} customers.", days_ago=i) for i in range(R.RECORD_LIMIT + 3)]
    record = _record(list(reversed(rows)))
    assert [line.event_id for line in record.lines] == [f"e{i:02d}" for i in range(R.RECORD_LIMIT)]
    assert record.cut == 3
    assert record.newest == "e00"


def test_nothing_after_the_instant_is_read():
    record = _record([_row("future", "We crossed 50 customers.", days_ago=-1),
                      _row("past", "We crossed 12 customers.", days_ago=1)])
    assert [line.event_id for line in record.lines] == ["past"]


def test_the_same_mail_twice_is_one_line():
    record = _record([_row("e1", "We crossed 12 customers."), _row("e1", "We crossed 12 customers.")])
    assert len(record.lines) == 1


def test_a_file_s_own_mail_is_left_to_its_timeline():
    record = _record([_row("mine", "We crossed 12 customers.", days_ago=1),
                      _row("other", "We crossed 11 customers.", days_ago=2)])
    assert [line.event_id for line in record.excluding({"mine"})] == ["other"]
    assert record.newest_excluding({"mine"}) == "other"
    assert record.newest_excluding({"mine", "other"}) is None


def test_an_empty_record_names_nothing():
    record = _record([])
    assert record.lines == () and record.cut == 0 and record.newest is None


def test_the_record_is_plain_data():
    record = _record([_row("evt_update", UPDATE)], unread=4)
    raw = record.as_dict()
    assert raw["unread"] == 4 and raw["lines"][0]["event_id"] == "evt_update"
    json.dumps(raw)


# ── the one read ───────────────────────────────────────────────────────────────────────────────

ORG = "org_company_record_test"
FOUNDER = "arjun.record@nimbuslabs.test"
#: The founder's own address at a public host — ours by the address alone, not by a domain.
PERSONAL = "arjun.record@gmail.test"


@pytest.fixture
def db():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the record reads Postgres")
    from sqlalchemy import create_engine, text

    engine = create_engine(url)                # the schema is applied at conftest import
    with engine.begin() as c:
        _wipe(c)
        c.execute(text("insert into orgs (id, name, email, company) values (:o, 'Arjun Rao', :e, "
                       "'Nimbus Labs')"), {"o": ORG, "e": f"{ORG}@tenant.test"})
        for kind, value in (("address", FOUNDER), ("domain", "nimbuslabs.test"),
                            ("address", PERSONAL)):
            c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                           "values (:o, :k, :v, 'test')"), {"o": ORG, "k": kind, "v": value})
    with engine.begin() as c:
        yield c
    with engine.begin() as c:
        _wipe(c)
    engine.dispose()


def _wipe(c) -> None:
    from sqlalchemy import text
    c.execute(text("delete from prepared_content where org_id = :o"), {"o": ORG})
    c.execute(text("delete from source_events where org_id = :o"), {"o": ORG})
    c.execute(text("delete from org_self_identities where org_id = :o"), {"o": ORG})
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _mail(c, event_id: str, sender: str, words: str | None, *, days_ago: float, outcome="emitted",
          scope: str | None = "org", source="gmail", object_type="email_message") -> None:
    from sqlalchemy import text
    at = NOW - timedelta(days=days_ago)
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        " source_object_id, parent_object_id, dedup_key, actor, occurred_at, captured_at, outcome, "
        " visibility_scope) values (:e, :o, 'con_gmail', :s, :t, :e, :th, :k, cast(:a as jsonb), :at, "
        " :at, :out, :scope)"),
        {"e": event_id, "o": ORG, "s": source, "t": object_type, "th": f"t_{event_id}",
         "k": f"{source}:{object_type}:{event_id}", "a": json.dumps({"email": sender, "name": "x"}),
         "at": at, "out": outcome, "scope": scope})
    if words is not None:
        c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
                       "values (:e, :o, :p, :w)"), {"e": event_id, "o": ORG, "p": f"pc_{event_id}",
                                                    "w": words})


@pytest.mark.pg
def test_the_read_keeps_our_kept_mail_and_reads_no_other(db):
    _mail(db, "evt_update", FOUNDER, UPDATE, days_ago=8)
    _mail(db, "evt_colleague", "harsh@nimbuslabs.test", "We shipped the iOS app.", days_ago=3)
    _mail(db, "evt_personal", PERSONAL, "We hired our first engineer.", days_ago=4)
    _mail(db, "evt_stranger", "someone@gmail.test", "We crossed 30 subscribers.", days_ago=5)
    _mail(db, "evt_subdomain", "ops@mail.nimbuslabs.test", "We signed the lease.", days_ago=6)
    _mail(db, "evt_theirs", "gautam@ridgelinecap.test", "We crossed 40 portfolio companies.",
          days_ago=2)
    _mail(db, "evt_archived", FOUNDER, "We crossed 99 customers.", days_ago=1, outcome="archived")
    _mail(db, "evt_private", FOUNDER, "We raised a bridge of 2 crore.", days_ago=1, scope="private")
    _mail(db, "evt_meeting", FOUNDER, "We crossed 50 customers.", days_ago=1, source="gcal",
          object_type="calendar_event")
    _mail(db, "evt_future", FOUNDER, "We crossed 70 customers.", days_ago=-2)
    record = R.read_company_record(db, ORG, now=NOW)
    assert [line.event_id for line in record.lines] == [
        "evt_colleague", "evt_personal", "evt_subdomain", "evt_update"], (
        "ours and kept only — by our address, our domain or a subdomain of it: not their mail, not a "
        "stranger at a public host, not an archive's words, not a private capture, not a meeting, "
        "nothing after the instant")
    assert record.names == ("Nimbus Labs",)
    update = record.lines[-1]
    assert "we crossed 12 paying customers this month" in update.said
    assert update.thread == "t_evt_update" and update.mailbox == "con_gmail"


@pytest.mark.pg
def test_the_read_counts_what_it_did_not_scan(db, monkeypatch):
    monkeypatch.setattr(R, "SCAN_LIMIT", 2)
    for i in range(5):
        _mail(db, f"evt_{i}", FOUNDER, f"We crossed {10 + i} customers.", days_ago=i + 1)
    record = R.read_company_record(db, ORG, now=NOW)
    assert [line.event_id for line in record.lines] == ["evt_0", "evt_1"]
    assert record.unread == 3


@pytest.mark.pg
def test_a_tenant_with_no_company_name_is_read_by_we_alone(db):
    from sqlalchemy import text
    db.execute(text("update orgs set company = null where id = :o"), {"o": ORG})
    _mail(db, "evt_name", FOUNDER, "Nimbus Labs crossed 12 customers.", days_ago=1)
    _mail(db, "evt_we", FOUNDER, "We crossed 12 customers.", days_ago=2)
    record = R.read_company_record(db, ORG, now=NOW)
    assert record.names == () and [line.event_id for line in record.lines] == ["evt_we"]


def test_the_reader_writes_nothing():
    """One read a sweep, and only a read: every SQL statement the module hands `text()` is a select."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(R.__file__).read_text())
    statements = [" ".join(ast.literal_eval(node.args[0]).split()).lower() for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "text"]
    assert statements, "the read is SQL handed to text()"
    for sql in statements:
        assert sql.startswith("select "), sql
        for verb in ("insert into", "update ", "delete from"):
            assert verb not in sql, sql

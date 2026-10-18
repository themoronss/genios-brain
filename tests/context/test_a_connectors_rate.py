"""STEP-10 · a connector's file says how many people it introduced, how many of them answered, and
how many of them it got onto a call — each a number that says what it rests on.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_connectors_rate.py -q

`context/workstreams.files_for` (tree `yc2_w27_s10 · M29.C4.L-logic.V0.U02`). Measured on the golden
set (`STEP-10` §8.1): Introly's rate — 8 introductions, 5 contacts replied, 1 call booked — could be
counted by SQL over the ledger and not from memory. STEP-09 made every introduction an `introduced`
edge, so the connector's file now carries the three: `introductions` (the people it introduced),
`replied` (of them, those who wrote to us themselves after their introduction — a responder is not
them) and `calls` (of them, those on a calendar meeting that starts after it). Each is a `Measured`
(`contracts/measured`), measured at the connector. Deterministic, no model, no table — and nothing a
seat captured privately is counted.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.capture.gate.rules import AUTO_REPLY
from genios_engine.context.workstreams import as_dict, files_for
from genios_engine.contracts.measured import MEASURED_HERE, count_of, rate_of

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, brief, later, mention, process,
                               reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s10_connector_rate"
RAHUL, FARAH, SIMON = "rahul@kestrelcap.test", "farah@kitepath.test", "simon@lumenpath.test"
BOARDY, NEEL = "hello@boardy.test", "neel@insightvc.test"
NOW = later(30)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _meeting(store, event_id: str, *, attendees, at, organizer: str = FOUNDER) -> None:
    """A calendar meeting as Layer 1 lands it (`capture/connectors/calendar.py`): its start is
    `occurred_at`, its attendees are `recipients`, its organiser the actor."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, recipients, occurred_at, captured_at, outcome) "
            "values (:e, :o, 'con_cal', 'gcal', 'calendar_event', :e, :k, cast(:a as jsonb), :r, "
            " :at, :at, 'emitted')"),
            {"e": event_id, "o": ORG, "k": f"gcal:calendar_event:{event_id}",
             "a": json.dumps({"type": "external_contact", "email": organizer}),
             "r": list(attendees), "at": at})


def _private(store, *event_ids: str) -> None:
    with store.engine.begin() as c:
        c.execute(text("update source_events set visibility_scope = 'private' "
                       " where org_id = :o and event_id = any(:e)"), {"o": ORG, "e": list(event_ids)})


def _world(store, *connectors: str):
    """Introly introduces Rahul and Farah, then Simon — who had written to us once before. Farah
    answers; Rahul's responder answers for him, we write to him and Introly nudges about him; we
    write to Simon; Introly asks something of its own. On the calendar: Simon before his
    introduction, Farah after hers, and a meeting Rahul set up after his. Boardy, the second
    connector, only asks."""
    b = brief(ORG, connectors=connectors or (CONNECTOR, BOARDY))
    for kw in (
            dict(event_id="evt_simon_early", sender=SIMON, thread="t_simon",
                 at=T0 - timedelta(days=5)),
            dict(event_id="evt_intro", sender=CONNECTOR, recipients=(FOUNDER, RAHUL, FARAH),
                 thread="t_intro", headers=UNSUBSCRIBE,
                 mentions=(mention("Rahul Menon"), mention("Farah Qureshi"),
                           mention("Kestrel Capital", "organization"),
                           mention("Kitepath", "organization"))),
            dict(event_id="evt_farah", sender=FARAH, recipients=(FOUNDER, CONNECTOR),
                 thread="t_intro", at=later(1)),
            dict(event_id="evt_rahul_ooo", sender=RAHUL, thread="t_intro", at=later(1),
                 availability_marker=AUTO_REPLY),
            dict(event_id="evt_intro_simon", sender=CONNECTOR, recipients=(FOUNDER, SIMON),
                 thread="t_intro2", headers=UNSUBSCRIBE,
                 mentions=(mention("Simon Das"), mention("Lumenpath", "organization")),
                 at=later(2)),
            dict(event_id="evt_to_rahul", sender=FOUNDER, recipients=(RAHUL,), thread="t_intro",
                 at=later(3)),
            dict(event_id="evt_to_simon", sender=FOUNDER, recipients=(SIMON,), thread="t_intro2",
                 at=later(3)),
            dict(event_id="evt_nudge", sender=CONNECTOR, thread="t_nudges", headers=UNSUBSCRIBE,
                 mentions=(mention("Rahul"),), at=later(3)),
            dict(event_id="evt_ask", sender=CONNECTOR, thread="t_ask", headers=UNSUBSCRIBE,
                 at=later(4)),
            dict(event_id="evt_boardy_ask", sender=BOARDY, thread="t_boardy",
                 headers=UNSUBSCRIBE, at=later(4))):
        process(store, ORG, company_brief=b, **kw)
    _meeting(store, "cal_simon_early", attendees=(FOUNDER, SIMON), at=later(1))
    _meeting(store, "cal_farah", attendees=(FOUNDER, FARAH), at=later(5))
    _meeting(store, "cal_rahul", organizer=RAHUL, attendees=(RAHUL, FOUNDER), at=later(6))
    return b


def _files(store, b) -> dict:
    with store.engine.connect() as c:
        return {f.counterparty_key: f for f in files_for(c, ORG, now=NOW, company_brief=b).files}


def _rate(f) -> tuple:
    return f.introductions, f.replied, f.calls


def test_a_connectors_file_counts_the_people_it_introduced(store):
    introly = _files(store, _world(store))["introly.test"]
    assert introly.kind == "connector"
    assert introly.introductions == count_of(3, basis="connector")


def test_of_them_only_those_who_wrote_to_us_themselves_after_their_introduction_replied(store):
    """Farah answered. Rahul did not: his responder did, we wrote to him, Introly nudged about him,
    and he set up a meeting — none of it a mail of his own. Simon wrote to us before he was
    introduced, which answers nothing."""
    introly = _files(store, _world(store))["introly.test"]
    assert introly.replied == rate_of(1, 3, basis="connector")


def test_an_auto_reply_is_never_their_answer_and_their_own_mail_is(store):
    b = _world(store)
    process(store, ORG, event_id="evt_rahul", sender=RAHUL, thread="t_intro", company_brief=b,
            at=later(7))
    assert _files(store, b)["introly.test"].replied == rate_of(2, 3, basis="connector")


def test_a_mail_written_before_the_introduction_answers_nothing(store):
    b = _world(store)
    process(store, ORG, event_id="evt_simon_after", sender=SIMON, thread="t_intro2",
            company_brief=b, at=later(7))
    assert _files(store, b)["introly.test"].replied == rate_of(2, 3, basis="connector")


def test_of_them_those_on_a_meeting_after_their_introduction_had_a_call(store):
    """Farah's meeting and the one Rahul set up start after their introductions; Simon's started a
    day before his, and our mail to him is no meeting."""
    introly = _files(store, _world(store))["introly.test"]
    assert introly.calls == rate_of(2, 3, basis="connector")


def test_a_meeting_before_the_introduction_is_no_call_and_one_after_it_is(store):
    b = _world(store)
    _meeting(store, "cal_simon_after", attendees=(SIMON, FOUNDER), at=later(9))
    assert _files(store, b)["introly.test"].calls == rate_of(3, 3, basis="connector")


def test_nothing_a_seat_captured_privately_is_counted(store):
    """Simon's introduction, Farah's answer and Farah's meeting were captured privately: two people
    introduced, none answered, one call — Rahul's."""
    b = _world(store)
    _private(store, "evt_intro_simon", "evt_farah", "cal_farah")
    assert _rate(_files(store, b)["introly.test"]) == (
        count_of(2, basis="connector"),
        rate_of(0, 2, basis="connector"), rate_of(1, 2, basis="connector"))


def test_one_person_introduced_twice_is_one_introduction(store):
    """Introly introduces Rahul again, and Farah once more from its second address — both of
    Introly's addresses the brief names, one file. Three people, still."""
    b = _world(store, CONNECTOR, "team@introly.test", BOARDY)
    process(store, ORG, event_id="evt_again", sender=CONNECTOR, recipients=(FOUNDER, RAHUL),
            thread="t_again", headers=UNSUBSCRIBE, mentions=(mention("Rahul Menon"),),
            company_brief=b, at=later(8))
    process(store, ORG, event_id="evt_team", sender="team@introly.test",
            recipients=(FOUNDER, FARAH), thread="t_team", headers=UNSUBSCRIBE,
            mentions=(mention("Farah Qureshi"),), company_brief=b, at=later(8))
    introly = _files(store, b)["introly.test"]
    assert introly.introductions == count_of(3, basis="connector")
    assert introly.replied == rate_of(1, 3, basis="connector")


def test_each_connector_counts_only_the_people_it_introduced(store):
    b = _world(store)
    process(store, ORG, event_id="evt_boardy_intro", sender=BOARDY, recipients=(FOUNDER, NEEL),
            thread="t_boardy_intro", headers=UNSUBSCRIBE, mentions=(mention("Neel Shah"),),
            company_brief=b, at=later(8))
    process(store, ORG, event_id="evt_neel", sender=NEEL, thread="t_boardy_intro",
            company_brief=b, at=later(9))
    files = _files(store, b)
    assert _rate(files["boardy.test"]) == (
        count_of(1, basis="connector"),
        rate_of(1, 1, basis="connector"), rate_of(0, 1, basis="connector"))
    assert files["introly.test"].introductions.n == 3


def test_a_connector_that_introduced_nobody_has_measured_nothing(store):
    """Boardy only asked. It introduced no one — a count of none, which is exact — and a rate of
    nobody is no rate: never a 0% that reads as a measurement."""
    boardy = _files(store, _world(store))["boardy.test"]
    assert boardy.kind == "connector"
    assert [(m.value, m.n, m.says()) for m in _rate(boardy)] == [
        (0, 0, "none"), (None, 0, "not measured"), (None, 0, "not measured")]


def test_only_a_connectors_file_carries_the_rate(store):
    files = _files(store, _world(store))
    assert {k for k, f in files.items() if f.kind == "connector"} == {"introly.test",
                                                                       "boardy.test"}
    for key, f in files.items():
        if f.kind != "connector":
            assert _rate(f) == (None, None, None), key


def test_each_number_says_what_it_rests_on(store):
    introly = _files(store, _world(store))["introly.test"]
    for m in _rate(introly):
        assert (m.n, m.basis, m.source) == (3, "connector", MEASURED_HERE)
    assert [(m.stat, m.sparse, m.says()) for m in _rate(introly)] == [
        ("count", False, "3"), ("rate", True, "1 of 3"), ("rate", True, "2 of 3")], (
        "a count is exact; three introductions are too few for a rate to be a habit")
    assert (introly.replied.unit, introly.calls.unit) == ("ratio", "ratio")
    assert "usually" not in introly.replied.says()


def test_the_read_model_carries_the_rate(store):
    b = _world(store)
    with store.engine.connect() as c:
        body = as_dict(files_for(c, ORG, now=NOW, company_brief=b), now=NOW)
    files = {f["counterparty"]["key"]: f for f in body["files"]}
    introly = files["introly.test"]
    assert introly["introductions"] == count_of(3, basis="connector").as_dict()
    assert introly["replied"] == rate_of(1, 3, basis="connector").as_dict()
    assert introly["calls"] == rate_of(2, 3, basis="connector").as_dict()
    assert (files["kestrelcap.test"]["introductions"], files["kestrelcap.test"]["replied"],
            files["kestrelcap.test"]["calls"]) == (None, None, None)

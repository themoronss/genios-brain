"""STEP-10 · a file's numbers — their reply time and yours, each with what it rests on; its bounces; what was checked.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_has_its_numbers.py -q

`context/workstream_numbers.numbers_for` (tree `yc2_w27_s10 · M29.C2.L-logic.V2.U04`). Measured (`STEP-10`
§8.1): the golden set's only reply times were "tenant normals" from one reply counted twice, with no n;
the founder's own existed nowhere; a bounce sat on the mail daemon; "no reply" was said over a mailbox
nobody had shown was read. Now each of a file's people carries their reply time and yours measured on
them at ANY n — one reply is "once: 1.92 days", never a habit (`06` D37) — beside the normals the waiting
pass wrote where a level holds five; a bounce; and the file names the mailboxes its mail came through and
whether "no reply since our last mail" may be said at all.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.periodic import _ensure_tenant_node
from genios_engine.context.waiting import compute_waiting
from genios_engine.context.workstream_numbers import as_dict, numbers_for
from genios_engine.context.workstream_timeline import timeline_for
from genios_engine.context.workstreams import files_for
from genios_engine.contracts.measured import Measured
from genios_engine.platform.self_identity import identity_for

from .workstream_world import FOUNDER, T0, extraction, ledger, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_file_numbers"
KAVITHA = "kavitha@inboxmail.test"
PRIYA = "priya@northwind.test"
FUND = "partners@lattice-capital.test"
NOW = T0 + timedelta(days=60)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        _ensure_tenant_node(pg_store, c, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _numbers(store, person: str, *, now=NOW):
    """The numbers of the one file this person is in — a company's file, when they work at one."""
    who = node(store, ORG, person).node_id
    with store.engine.connect() as c:
        [file] = [f for f in files_for(c, ORG, now=now).files if who in f.people]
        return numbers_for(c, ORG, file, timeline_for(c, ORG, file.file_id, now=now), now=now)


def _person(numbers, key: str):
    [p] = [p for p in numbers.people if p.key == key]
    return p


def _kavitha_answers_once(store):
    """F25's shape: one reply, 1.92 days after our offer."""
    process(store, ORG, event_id="evt_offer", sender=FOUNDER, recipients=(KAVITHA,),
            thread="t_offer", at=T0)
    process(store, ORG, event_id="evt_yes", sender=KAVITHA, thread="t_offer",
            at=T0 + timedelta(days=1.92))


def _priya_and_us(store):
    """Five times we wrote and Priya answered (1, 2, 2, 3, 9 days); five times she wrote and we
    answered (0.5, 1, 1, 2, 3 days)."""
    for i, gap in enumerate((1, 2, 2, 3, 9)):
        asked = T0 + timedelta(days=5 * i)
        process(store, ORG, event_id=f"evt_ask_{i}", sender=FOUNDER, recipients=(PRIYA,),
                thread=f"t_a{i}", at=asked)
        process(store, ORG, event_id=f"evt_her_{i}", sender=PRIYA, thread=f"t_a{i}",
                at=asked + timedelta(days=gap))
    for i, gap in enumerate((0.5, 1, 1, 2, 3)):
        asked = T0 + timedelta(days=30 + 5 * i)
        process(store, ORG, event_id=f"evt_she_{i}", sender=PRIYA, thread=f"t_b{i}", at=asked)
        process(store, ORG, event_id=f"evt_we_{i}", sender=FOUNDER, recipients=(PRIYA,),
                thread=f"t_b{i}", at=asked + timedelta(days=gap))


def test_one_reply_is_their_reply_time_once_never_a_normal(store):
    _kavitha_answers_once(store)
    compute_waiting(store, ORG, now=NOW)
    kavitha = _person(_numbers(store, KAVITHA), KAVITHA)
    assert kavitha.their_reply_time == Measured(value=1.92, n=1, basis="person", unit="days")
    assert kavitha.their_reply_time.says() == "once: 1.92 days"
    assert kavitha.their_normal is None, "no level holds five replies"
    assert kavitha.your_reply_time.says() == "not measured", "she never wrote first"


def test_five_replies_are_their_normal_and_five_answers_are_yours(store):
    _priya_and_us(store)
    compute_waiting(store, ORG, now=NOW)
    numbers = _numbers(store, PRIYA)
    priya = _person(numbers, PRIYA)
    assert priya.their_reply_time == Measured(value=2.0, n=5, basis="person", unit="days")
    assert priya.their_normal == Measured(value=2.0, n=5, basis="person", unit="days")
    assert priya.your_reply_time == Measured(value=1.0, n=5, basis="person", unit="days")
    assert priya.your_normal == Measured(value=1.0, n=5, basis="person", unit="days")
    assert numbers.your_normal_overall == Measured(value=1.0, n=5, basis="tenant", unit="days")


def test_their_normal_says_the_level_it_was_measured_at(store):
    """Kavitha replied once; the tenant holds Priya's five: her normal is the tenant's, and says so."""
    _priya_and_us(store)
    _kavitha_answers_once(store)
    compute_waiting(store, ORG, now=NOW)
    kavitha = _person(_numbers(store, KAVITHA), KAVITHA)
    assert kavitha.their_reply_time.n == 1
    assert (kavitha.their_normal.basis, kavitha.their_normal.n) == ("tenant", 6)


def test_a_bounce_is_on_the_person_it_failed_to_reach(store):
    process(store, ORG, event_id="evt_pitch", sender=FOUNDER, recipients=(FUND,), thread="t_pitch",
            at=T0)
    us = identity_for(store, ORG)
    body = (f"** Address not found **\n\nYour message wasn't delivered to {FUND} because the domain "
            "couldn't be found.")
    ledger(store, ORG, event_id="evt_dsn", sender="mailer-daemon@mailhost.test", thread="t_pitch",
           at=T0 + timedelta(seconds=20), recipients=(FOUNDER,))
    pipeline.process_event(
        org_id=ORG, event_id="evt_dsn", source="gmail",
        content="Delivery Status Notification (Failure)\n\n" + body,
        sender_email="mailer-daemon@mailhost.test", sender_name="Mail Delivery Subsystem",
        recipient_emails=[FOUNDER], occurred_at=T0 + timedelta(seconds=20), llm=None,
        store=store, is_inbound=True, internal_emails=us.addresses, self_identity=us,
        thread_id="t_pitch", canon_meta={"subject": "Delivery Status Notification (Failure)",
                                          "body": body, "headers": {}},
        qualified_extraction=extraction())
    numbers = _numbers(store, FUND)
    assert _person(numbers, FUND).bounced_at == T0 + timedelta(seconds=20)


def _mailbox(store, *, finished, completed=True, days=90, cid="con_x"):
    with store.engine.begin() as c:
        c.execute(text(
            "insert into connections (connection_id, org_id, source_type, external_account_id, "
            " capture_scope, status) values (:c, :o, 'gmail', null, cast(:s as jsonb), "
            " 'connected') on conflict do nothing"),
            {"c": cid, "o": ORG, "s": json.dumps({"backfill_days": days})})
        c.execute(text(
            "insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, scanned, "
            " claimed_total, cursor_exhausted, error, started_at, finished_at) values (:r, :o, :c, "
            " 'gmail', 'incremental', 1, 1, :x, null, :at, :at)"),
            {"r": f"run_{cid}_{finished.isoformat()}", "o": ORG, "c": cid, "x": completed,
             "at": finished})


def test_no_reply_may_be_said_only_over_a_mailbox_that_has_looked_since(store):
    _kavitha_answers_once(store)
    process(store, ORG, event_id="evt_again", sender=FOUNDER, recipients=(KAVITHA,),
            thread="t_offer", at=T0 + timedelta(days=10))
    _mailbox(store, finished=T0 + timedelta(days=9))
    before = _numbers(store, KAVITHA)
    assert before.no_reply_since == T0 + timedelta(days=10)
    assert [m.connection_id for m in before.mailboxes] == ["con_x"]
    assert before.no_reply_can_be_said is False, "the last sync ended before our mail went"
    _mailbox(store, finished=T0 + timedelta(days=12))
    assert _numbers(store, KAVITHA).no_reply_can_be_said is True


def test_an_unfinished_sync_vouches_for_nothing(store):
    _kavitha_answers_once(store)
    _mailbox(store, finished=T0 + timedelta(days=12), completed=False)
    assert _numbers(store, KAVITHA).no_reply_can_be_said is False


def test_a_file_with_no_mail_of_ours_has_no_silence_to_vouch_for(store):
    process(store, ORG, event_id="evt_hello", sender=KAVITHA, thread="t_hello", at=T0)
    _mailbox(store, finished=T0 + timedelta(days=12))
    numbers = _numbers(store, KAVITHA)
    assert (numbers.no_reply_since, numbers.no_reply_can_be_said) == (None, False)


def test_only_the_files_own_mailboxes_are_on_its_receipt(store):
    _kavitha_answers_once(store)
    _mailbox(store, finished=T0 + timedelta(days=12))
    _mailbox(store, finished=T0 + timedelta(days=12), cid="con_other_mailbox")
    assert [m.connection_id for m in _numbers(store, KAVITHA).mailboxes] == ["con_x"]


def test_the_numbers_read_as_json(store):
    _priya_and_us(store)
    compute_waiting(store, ORG, now=NOW)
    body = as_dict(_numbers(store, PRIYA))
    [priya] = body["people"]
    assert priya["key"] == PRIYA
    assert priya["their_reply_time"] == Measured(value=2.0, n=5, basis="person",
                                                 unit="days").as_dict()
    assert priya["your_normal"]["says"] == "usually 1 days (n=5, person)"
    assert body["your_normal_overall"]["basis"] == "tenant"
    assert (body["mailboxes"], body["no_reply_can_be_said"]) == ([], False)
    assert priya["bounced_at"] is None and body["file_id"]


def test_a_normal_with_no_n_beside_it_is_no_normal(store):
    """A cadence an earlier pass wrote before STEP-10 carried no n: it cannot say what it rests on."""
    _kavitha_answers_once(store)
    kavitha = node(store, ORG, KAVITHA).node_id
    with store.engine.begin() as c:
        c.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            " value, value_type, status, authority_rank, confidence, occurred_at, valid_from) "
            "values ('fv_old_cadence', 'f_old_cadence', :o, :n, 'party.reply_cadence_days', "
            "        cast('1.92' as jsonb), 'number', 'active', 2, 0.9, :at, :at)"),
            {"o": ORG, "n": kavitha, "at": T0})
    assert _person(_numbers(store, KAVITHA), KAVITHA).their_normal is None


def test_a_private_fact_is_no_files_number(store):
    _priya_and_us(store)
    compute_waiting(store, ORG, now=NOW)
    with store.engine.begin() as c:
        c.execute(text("update graph_facts set visibility_scope = 'private' where org_id = :o "
                       "   and field like 'party.reply_cadence%'"), {"o": ORG})
    priya = _person(_numbers(store, PRIYA), PRIYA)
    assert priya.their_normal is None
    assert priya.their_reply_time.n == 5, "measured from the ledger, not from the private fact"


def test_a_companys_file_shows_each_of_its_people_in_order(store):
    for who, at in (("ravi@northwind.test", T0), (PRIYA, T0 + timedelta(days=1))):
        process(store, ORG, event_id=f"evt_{who}", sender=who, thread=f"t_{who}", at=at)
    assert [p.key for p in _numbers(store, PRIYA).people] == [PRIYA, "ravi@northwind.test"]

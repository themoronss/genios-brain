"""STEP-10 · a file shows a bounce while it is still the latest word between us — and the latest report's time.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_bounce_is_shown_while_it_stands.py -q

`context/workstream_numbers.numbers_for` (tree `yc2_w27_s10 · M29.C3.L-logic.V2.U06`). Found by STEP-10's
crosscheck (X1): a file showed `bounced_at` while `delivery.status = failed` stood, and that fact is never
retired — so a partner whose mailbox was full one day and who wrote to us a week later still read "bounced".
And the time it showed was the FIRST report's: a second report on an address writes the same value, which the
store keeps as a corroborating reference on the first one's fact (`graph_store.fact_write_action`: "noop"),
so a pitch that bounced after an older one did read the older bounce. The wait already read both right (it
compares times, and reads every report — `waiting._bounced_since_our_last_mail`); the display did not.

Now the file shows the latest report behind the fact, and only while nothing has passed between us since:
they wrote (the address works), or we wrote again (a newer mail is a new attempt — if it bounces too, its own
report is the one shown).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.context.waiting import compute_waiting
from genios_engine.context.workstream_numbers import as_dict, numbers_for
from genios_engine.context.workstream_timeline import timeline_for
from genios_engine.context.workstreams import files_for
from genios_engine.platform.self_identity import identity_for

from .workstream_world import FOUNDER, T0, extraction, ledger, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_bounce_stands"
FUND = "partners@lattice-capital.test"
DAEMON = "mailer-daemon@mailhost.test"
NOW = T0 + timedelta(days=30)
REPORT = ("Delivery Status Notification (Failure)",
          "** Address not found **\n\nYour message wasn't delivered to {to} because the address "
          "couldn't be found, or is unable to receive mail.")


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _ours(store, event_id: str, *, at, thread: str) -> None:
    process(store, ORG, event_id=event_id, sender=FOUNDER, recipients=(FUND,), thread=thread, at=at)


def _theirs(store, event_id: str, *, at, thread: str) -> None:
    process(store, ORG, event_id=event_id, sender=FUND, thread=thread, at=at)


def _report(store, event_id: str, *, at, thread: str) -> None:
    """The daemon's report on our mail in `thread`, kept by the gate and read by the pipeline."""
    us = identity_for(store, ORG)
    subject, body = REPORT[0], REPORT[1].format(to=FUND)
    ledger(store, ORG, event_id=event_id, sender=DAEMON, thread=thread, at=at, recipients=(FOUNDER,))
    pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=f"{subject}\n\n{body}",
        sender_email=DAEMON, sender_name="Mail Delivery Subsystem", recipient_emails=[FOUNDER],
        occurred_at=at, llm=None, store=store, is_inbound=True, internal_emails=us.addresses,
        self_identity=us, thread_id=thread,
        canon_meta={"subject": subject, "body": body, "headers": {}},
        qualified_extraction=extraction())


def _fund(store):
    who = node(store, ORG, FUND).node_id
    with store.engine.connect() as c:
        [file] = [f for f in files_for(c, ORG, now=NOW).files if who in f.people]
        numbers = numbers_for(c, ORG, file, timeline_for(c, ORG, file.file_id, now=NOW), now=NOW)
    [fund] = [p for p in numbers.people if p.key == FUND]
    return fund, numbers


def _waited_on(store) -> bool:
    compute_waiting(store, ORG, now=NOW)
    with store.engine.connect() as c:
        return c.execute(text(
            "select count(*) from graph_facts f join graph_nodes n on n.org_id = f.org_id "
            "   and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = :k and f.field = 'thread.days_waiting' "
            "   and f.valid_to is null"), {"o": ORG, "k": FUND}).scalar() > 0


def _pitch_and_bounce(store):
    _ours(store, "evt_pitch", at=T0, thread="t-pitch")
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20), thread="t-pitch")


def test_a_bounce_with_nothing_since_is_shown(store):
    _pitch_and_bounce(store)
    assert _fund(store)[0].bounced_at == T0 + timedelta(seconds=20)


def test_their_older_mail_does_not_hide_a_later_bounce(store):
    _theirs(store, "evt_hello", at=T0 - timedelta(days=3), thread="t-hello")
    _pitch_and_bounce(store)
    assert _fund(store)[0].bounced_at == T0 + timedelta(seconds=20)


def test_they_wrote_since_and_the_address_works(store):
    """X1's case: the mailbox was full one day; a week later they wrote."""
    _pitch_and_bounce(store)
    _theirs(store, "evt_back", at=T0 + timedelta(days=7), thread="t-back")
    assert _fund(store)[0].bounced_at is None


def test_we_wrote_again_and_nothing_bounced(store):
    _pitch_and_bounce(store)
    _ours(store, "evt_again", at=T0 + timedelta(days=5), thread="t-again")
    assert _fund(store)[0].bounced_at is None


def test_a_second_bounce_is_the_one_shown(store):
    """The second report writes `failed` again — a corroboration on the first one's fact, whose own
    time is the first report's. The file reads every report behind the fact, and shows the latest."""
    _pitch_and_bounce(store)
    _ours(store, "evt_again", at=T0 + timedelta(days=5), thread="t-again")
    _report(store, "evt_dsn_again", at=T0 + timedelta(days=5, seconds=30), thread="t-again")
    assert _fund(store)[0].bounced_at == T0 + timedelta(days=5, seconds=30)


def test_a_mail_at_the_reports_own_instant_leaves_it_standing(store):
    """The boundary: a mail at or before the report leaves it standing; only one after it ends it."""
    _ours(store, "evt_pitch", at=T0, thread="t-pitch")
    _report(store, "evt_dsn", at=T0, thread="t-pitch")
    assert _fund(store)[0].bounced_at == T0


def test_a_status_that_is_not_failed_is_no_bounce(store):
    """Whatever later supersedes `failed` on the address, the file no longer reads a bounce from it."""
    _pitch_and_bounce(store)
    later = T0 + timedelta(days=2)
    ledger(store, ORG, event_id="evt_status", sender=DAEMON, thread="t-pitch", at=later,
           recipients=(FOUNDER,))
    with store.engine.begin() as c:
        assert store.write_fact(
            c, org_id=ORG, subject_node_id=node(store, ORG, FUND).node_id, field="delivery.status",
            value="delivered", value_type="enum", confidence=0.9, occurred_at=later,
            event_id="evt_status", evidence={}, source="gmail", authority_rank=2)
    assert _fund(store)[0].bounced_at is None


@pytest.mark.parametrize("private", [
    "update graph_facts set visibility_scope = 'private' where org_id = :o "
    "   and field = 'delivery.status'",
    "update source_events set visibility_scope = 'private' where org_id = :o "
    "   and event_id = 'evt_dsn'"])
def test_a_private_bounce_is_no_files_number(store, private):
    """A file is an org-level reader: a private fact, or a report only a seat may read, is not on it."""
    _pitch_and_bounce(store)
    with store.engine.begin() as c:
        c.execute(text(private), {"o": ORG})
    assert _fund(store)[0].bounced_at is None


def test_a_report_after_the_instant_asked_about_is_not_seen(store):
    """As of an instant: a report that came after it is not on the file yet."""
    _ours(store, "evt_pitch", at=T0, thread="t-pitch")
    _report(store, "evt_dsn_late", at=NOW + timedelta(days=1), thread="t-pitch")
    assert _fund(store)[0].bounced_at is None


@pytest.mark.parametrize("story, shown", [
    ("bounced", True), ("wrote again", False), ("bounced again", True)])
def test_the_file_and_the_wait_read_one_bounce(store, story, shown):
    """A bounce shown is a wait ended, and a newer mail of ours is a new wait with no bounce shown."""
    _pitch_and_bounce(store)
    if story != "bounced":
        _ours(store, "evt_again", at=T0 + timedelta(days=5), thread="t-again")
    if story == "bounced again":
        _report(store, "evt_dsn_again", at=T0 + timedelta(days=5, seconds=30), thread="t-again")
    assert (_fund(store)[0].bounced_at is not None, _waited_on(store)) == (shown, not shown)


def test_the_bounce_reads_as_json(store):
    _pitch_and_bounce(store)
    _fund_numbers = _fund(store)[1]
    [fund] = as_dict(_fund_numbers)["people"]
    assert fund["bounced_at"] == (T0 + timedelta(seconds=20)).isoformat()

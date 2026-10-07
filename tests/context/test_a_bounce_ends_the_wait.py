"""STEP-10 · a mail that bounced is not waited on — until we write to them again.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_bounce_ends_the_wait.py -q

`context/waiting.compute_waiting` (tree `yc2_w27_s10 · M29.C3.L-logic.V2.U03`, `06` D38). Measured on the lead
branch after the bounce units landed: a kept report writes `delivery.status = failed` on the fund partner and a
`delivery_failure` observation on the partner and on the thread (`context/delivery`) — and the partner still read
`days_waiting = 10`: the founder was told to wait for a reply to a mail that never arrived. Now a counterparty
whose LATEST mail from us bounced is not waited on: the waiting-only facts are retired, on the person and on the
thread. A newer mail to them is a new wait; a delay notice is no failure; a bounce of one recipient ends nobody
else's wait.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import bindparam, text

from genios_engine.context import pipeline
from genios_engine.context.waiting import WAITING_ONLY_FIELDS, compute_waiting
from genios_engine.platform.self_identity import identity_for

from .workstream_world import FOUNDER, T0, extraction, ledger, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_bounce_ends_wait"
FUND = "partners@lattice-capital.test"
OTHER = "ana@southwind.test"
DAEMON = "mailer-daemon@mailhost.test"
THREAD = "t-pitch"
NOW = T0 + timedelta(days=10)

#: Gmail's failure report (`capture/delivery_status`'s fixtures, as `test_a_bounce_is_on_the_file` uses it).
FAILED = ("Delivery Status Notification (Failure)",
          "** Address not found **\n\nYour message wasn't delivered to {to} because the domain "
          "couldn't be found. Check for typos or unnecessary spaces and try again.")
DELAYED = ("Delivery Status Notification (Delay)",
           "** Message not delivered yet **\n\nThere was a temporary problem delivering your message "
           "to {to}. Gmail will retry for 46 more hours. You'll be notified if the delivery fails "
           "permanently.")


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _pitch(store, event_id: str, *, at, to=(FUND,)) -> None:
    process(store, ORG, event_id=event_id, sender=FOUNDER, recipients=to, thread=THREAD, at=at)


def _report(store, event_id: str, *, at, to: str = FUND, shape=FAILED) -> None:
    """The daemon's report, kept by the gate and handed to the pipeline with its stored payload."""
    us = identity_for(store, ORG)
    subject, body = shape[0], shape[1].format(to=to)
    ledger(store, ORG, event_id=event_id, sender=DAEMON, thread=THREAD, at=at,
           recipients=(FOUNDER,))
    pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=f"{subject}\n\n{body}",
        sender_email=DAEMON, sender_name="Mail Delivery Subsystem", recipient_emails=[FOUNDER],
        occurred_at=at, llm=None, store=store, is_inbound=True, internal_emails=us.addresses,
        self_identity=us, thread_id=THREAD,
        canon_meta={"subject": subject, "body": body, "headers": {}},
        qualified_extraction=extraction())


def _waiting(store, key: str) -> dict:
    with store.engine.connect() as c:
        return {r.field: r.value for r in c.execute(text(
            "select f.field, f.value from graph_facts f join graph_nodes n "
            "  on n.org_id = f.org_id and n.node_id = f.subject_node_id and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = :k and f.valid_to is null "
            "   and f.field in :fields").bindparams(bindparam("fields", expanding=True)),
            {"o": ORG, "k": key, "fields": list(WAITING_ONLY_FIELDS)})}


def test_without_a_bounce_we_wait(store):
    _pitch(store, "evt_pitch", at=T0)
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND)["thread.days_waiting"] == 10


def test_a_bounced_mail_is_not_waited_on(store):
    _pitch(store, "evt_pitch", at=T0)
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND) == {}, "waiting on a reply to a mail that never arrived"
    assert _waiting(store, f"thread:{THREAD}") == {}, "the thread still waits"


def test_the_wait_a_bounce_ends_is_retired_not_left_standing(store):
    _pitch(store, "evt_pitch", at=T0)
    compute_waiting(store, ORG, now=T0 + timedelta(days=1))
    assert "thread.days_waiting" in _waiting(store, FUND)
    _report(store, "evt_dsn", at=T0 + timedelta(days=1, hours=2))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND) == {}


def test_a_newer_mail_after_the_bounce_is_a_new_wait(store):
    _pitch(store, "evt_pitch", at=T0)
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    _pitch(store, "evt_again", at=T0 + timedelta(days=3))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND)["thread.days_waiting"] == 7


def test_a_delay_notice_is_no_failure(store):
    _pitch(store, "evt_pitch", at=T0)
    _report(store, "evt_delay", at=T0 + timedelta(hours=1), shape=DELAYED)
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND)["thread.days_waiting"] == 10


def test_one_recipients_bounce_ends_nobody_elses_wait(store):
    """One pitch to two people: Lattice's address bounced, Southwind's arrived."""
    _pitch(store, "evt_pitch", at=T0, to=(FUND, OTHER))
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND) == {}
    assert _waiting(store, OTHER)["thread.days_waiting"] == 10
    assert _waiting(store, f"thread:{THREAD}")["thread.days_waiting"] == 10, (
        "the thread still waits on Southwind")


def test_our_own_copy_is_not_a_recipient_who_could_answer(store):
    """The founder copied themself: the only outside recipient bounced, so the thread waits on no one."""
    _pitch(store, "evt_pitch", at=T0, to=(FUND, FOUNDER))
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, f"thread:{THREAD}") == {}


def test_the_threads_last_mail_decides(store):
    """First to both, then a follow-up to Lattice alone — and that one bounced."""
    _pitch(store, "evt_pitch", at=T0, to=(FUND, OTHER))
    process(store, ORG, event_id="evt_ana", sender=OTHER, thread=THREAD,
            at=T0 + timedelta(days=1))
    _pitch(store, "evt_nudge", at=T0 + timedelta(days=2))
    _report(store, "evt_dsn", at=T0 + timedelta(days=2, seconds=20))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, f"thread:{THREAD}") == {}


def test_a_thread_whose_last_mail_names_no_one_keeps_waiting(store):
    _pitch(store, "evt_pitch", at=T0)
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    with store.engine.begin() as c:
        c.execute(text("update source_events set recipients = '{}' "
                       " where org_id = :o and event_id = 'evt_pitch'"), {"o": ORG})
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, f"thread:{THREAD}")["thread.days_waiting"] == 10, (
        "nobody named is not everybody bounced")


def test_a_second_bounce_after_the_resend_ends_the_new_wait(store):
    _pitch(store, "evt_pitch", at=T0)
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    _pitch(store, "evt_again", at=T0 + timedelta(days=3))
    _report(store, "evt_dsn_2", at=T0 + timedelta(days=3, seconds=20))
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND) == {}


def test_a_retracted_bounce_ends_nothing(store):
    _pitch(store, "evt_pitch", at=T0)
    _report(store, "evt_dsn", at=T0 + timedelta(seconds=20))
    with store.engine.begin() as c:
        c.execute(text("update graph_observations set status = 'retracted' "
                       " where org_id = :o and kind = 'delivery_failure'"), {"o": ORG})
    compute_waiting(store, ORG, now=NOW)
    assert _waiting(store, FUND)["thread.days_waiting"] == 10

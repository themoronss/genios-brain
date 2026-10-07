"""STEP-10 · a wave is one object — one pitch to five funds is ONE wave even with no qualified signal
behind it, and it says who it went to, who answered, whose address bounced, whom we wrote to again,
and how long since its last send.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_wave_is_one_object.py -q

`context/correlation_conversation.find_waves` (tree `yc2_w27_s10 · M29.C4.L-logic.V2.U01`). Measured
(`STEP-10` §8.1, golden F15): the founder sent one pitch to five funds and memory held five
`awaiting_response` readings, five dormant fund situations, five open loops and ten
`analytic_movement` — and no campaign, because the sentence rule inner-joins `qualified_signals` and
the founder's own mail there published none. A wave is now recognised two ways, in this order: the same
sentence (today's campaign rule, unchanged), else the same SUBJECT — the one Layer 1 wrote at the head
of the prepared text, with case, whitespace and a leading `Re:`/`Fwd:` chain set aside — sent by us
within seven days to three or more outside addresses (outside: not us by `platform/self_identity`).
Each wave says who it went to (each once); who wrote to us after their send (the ledger's actor, never
the turn memory keeps — a responder, a mailing or spam is not them); whose address carries
`delivery.status = failed` from a report at or after their send (`context/delivery`); whom we wrote to
again after their first send; and the days since its last send, on the sweep's clock. The counts are
`Measured` at basis "wave"; a share is `rate_of(k, n)`.

Every mail here goes through the real seams: our sends and their answers through
`context/pipeline.process_event` with the ledger row Layer 1 writes (`workstream_world`), the prepared
text through Layer 1's own `capture/pipeline.capture_event`, a bounce through the delivery report
`context/delivery` reads, and a qualified sentence as `capture/esqe`'s publisher stores it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture import pipeline as layer_1
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.rules import AUTO_REPLY
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.prepared_store import InMemoryPreparedContentStore
from genios_engine.context import pipeline
from genios_engine.context.correlation_conversation import (BY_SENTENCE, BY_SUBJECT,
                                                            WAVE_WINDOW_DAYS, find_campaigns,
                                                            find_waves, normalise_subject,
                                                            subject_of)
from genios_engine.contracts.measured import rate_of
from genios_engine.platform.self_identity import identity_for

from .workstream_world import FOUNDER, extraction, ledger, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_wave"
OTHER = "org_s10_wave_other"

#: Golden F15 — five funds, one pitch, an hour apart, each in its own Gmail thread.
FUNDS = {"Cobalt Peak": "partners@cobaltpeak.test", "Juniper Ridge": "hello@juniperridge.test",
         "Lattice Capital": "deals@latticecap.test", "Meridian Seed": "team@meridianseed.test",
         "Northstar Angels": "invest@northstarangels.test"}
COBALT, JUNIPER, LATTICE, MERIDIAN, NORTHSTAR = FUNDS.values()
SUBJECT = "Nimbus Labs - raising our seed round"
BODY = ("Hi {name} team,\n\nNimbus Labs is raising a seed round to build an AI chief of staff for "
        "founders. Our deck is attached; could we find 20 minutes in the next two weeks?\n\n"
        "Arjun Rao\nFounder, Nimbus Labs")
#: A colleague: an address at the domain the founder declared ours (`workstream_world.tenant`).
COLLEAGUE = "priya@nimbuslabs.test"
DAEMON = "mailer-daemon@mailhost.test"
#: A sentence long enough for the campaign rule (`MIN_SENTENCE_CHARS`), as L1 would quote it.
PITCH = "Nimbus Labs is raising a seed round to build an AI chief of staff for founders."

WAVE = datetime(2026, 8, 11, 1, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)          # F15's third sweep
SINCE = NOW - timedelta(days=90)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    tenant(pg_store, OTHER)
    yield pg_store
    reset(pg_store, ORG)
    reset(pg_store, OTHER)


# ── the world ────────────────────────────────────────────────────────────────────────────────────

def _prepared(subject: str, body: str) -> str:
    """The text Layer 1 stores for a mail it keeps — `capture_event` itself, with in-memory stores —
    so the subject read here is the one Layer 1 wrote, wherever Layer 1 writes it."""
    kept = InMemoryPreparedContentStore()
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m",
                    occurred_at=WAVE, actor_email=FOUNDER, actor_type="internal_user",
                    raw={"subject": subject, "body": body, "labelIds": ["SENT"]})
    result = layer_1.capture_event(raw, org_id=ORG, connection_id="conn_gmail",
                                   repo=InMemorySourceEventRepository(), prepared_store=kept,
                                   mailbox_owner=FOUNDER)
    assert result.outcome == "emitted", f"Layer 1 did not keep the fixture's mail: {result.outcome}"
    [row] = kept.rows.values()
    return row["prepared"].clean_text


def send(store, event_id: str, *, to, at, subject: str = SUBJECT, body: str | None = None,
         thread: str | None = None, org: str = ORG, prepared: bool = True) -> None:
    """One mail of ours as the drain lands it: the ledger row and `process_event`, and the prepared
    text Layer 1 stored when it kept it (`prepared=False`: none — an archive, or one aged out)."""
    process(store, org, event_id=event_id, sender=FOUNDER, recipients=tuple(to), thread=thread,
            at=at)
    if prepared:
        with store.engine.begin() as c:
            c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, "
                           " clean_text) values (:e, :o, :p, :t)"),
                      {"e": event_id, "o": org, "p": f"pc_{event_id}",
                       "t": _prepared(subject, body or BODY.format(name="there"))})


def reply(store, event_id: str, *, sender: str, at, thread: str | None = None,
          responder: bool = False) -> None:
    """Their mail to us. `responder`: an out-of-office answering for them (`email_noise:auto_reply`)."""
    process(store, ORG, event_id=event_id, sender=sender, thread=thread, at=at,
            availability_marker=AUTO_REPLY if responder else None)


def bounce(store, event_id: str, *, address: str, at, thread: str | None = None) -> None:
    """The mail daemon's failure report for `address`, through the pipeline the way the drain hands
    a read mail — `context/delivery` writes `delivery.status = failed` on the address."""
    subject = "Delivery Status Notification (Failure)"
    body = (f"** Address not found **\n\nYour message wasn't delivered to {address} because the "
            "domain couldn't be found. Check for typos or unnecessary spaces and try again.")
    us = identity_for(store, ORG)
    ledger(store, ORG, event_id=event_id, sender=DAEMON, thread=thread, at=at, recipients=(FOUNDER,))
    pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=f"{subject}\n\n{body}",
        sender_email=DAEMON, sender_name="Mail Delivery Subsystem", recipient_emails=[FOUNDER],
        occurred_at=at, llm=None, store=store, is_inbound=True, internal_emails=us.addresses,
        self_identity=us, thread_id=thread,
        canon_meta={"subject": subject, "body": body, "headers": {}},
        qualified_extraction=extraction())


def qualified(store, event_id: str, quote: str, *, at) -> None:
    """The qualified signal L1 publishes for a mail, with the sentence it quoted (the shape
    `capture/esqe/publisher` stores, as `tests/l1_supply.py` seeds it)."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
            " importance_bp, importance_version, confidence_bp, visibility, extraction_ref, "
            " evidence_refs, importance_components, state, occurred_at) "
            "values (:s, :o, :e, :tr, 'commitment_made', 5000, 'alg17-v1', 8000, "
            " cast('{\"scope\": \"org\"}' as jsonb), :x, cast(:refs as jsonb), "
            " cast('{}' as jsonb), 'active', :t)"),
            {"s": f"sig_{event_id}", "o": ORG, "e": event_id, "tr": f"tr_{event_id}",
             "x": f"l1:{event_id}", "t": at,
             "refs": json.dumps([{"source_ref": f"prepared_content:{event_id}", "quote": quote,
                                  "verified": True}])})


def private(store, event_id: str) -> None:
    with store.engine.begin() as c:
        c.execute(text("update source_events set visibility_scope = 'private' "
                       " where org_id = :o and event_id = :e"), {"o": ORG, "e": event_id})


def the_wave(store, *, org: str = ORG, funds=tuple(FUNDS.items()), start=WAVE,
             subject: str = SUBJECT, prefix: str = "to") -> list[str]:
    """F15's pitch: each fund its own mail and thread, an hour apart. Returns the event ids."""
    sent = []
    for i, (name, fund) in enumerate(funds, start=1):
        event_id = f"{org}_{prefix}{i}"
        send(store, event_id, to=(fund,), thread=f"t-{prefix}-{i}", at=start + timedelta(hours=i - 1),
             subject=subject, body=BODY.format(name=name), org=org)
        sent.append(event_id)
    return sent


def f15(store) -> list[str]:
    """F15's shape and what came of it: Lattice's address bounced twenty seconds after its send,
    Cobalt Peak answered two days on, and Juniper Ridge heard from us again nine days on."""
    sent = the_wave(store)
    bounce(store, "evt_bounce", address=LATTICE, thread="t-to-3",
           at=WAVE + timedelta(hours=2, seconds=20))
    reply(store, "evt_cobalt", sender=COBALT, thread="t-to-1", at=WAVE + timedelta(days=2))
    send(store, "evt_nudge", to=(JUNIPER,), subject=f"Re: {SUBJECT}", thread="t-to-2",
         at=WAVE + timedelta(days=9), body="Following up on the note below; happy to share more.")
    return sent


def waves(store, *, org: str = ORG, now: datetime = NOW, **kw):
    with store.engine.connect() as c:
        return find_waves(c, org, since=SINCE, now=now, **kw)


# ── F15: one pitch, five funds, one wave ─────────────────────────────────────────────────────────

def test_one_pitch_to_five_funds_with_no_qualified_signal_is_one_wave(store):
    sent = f15(store)
    with store.engine.connect() as c:
        assert find_campaigns(c, ORG, since=SINCE) == (), "the sentence rule has nothing to read"
    [wave] = waves(store)
    assert wave.recognised_by == BY_SUBJECT
    assert wave.line == SUBJECT
    assert wave.recipients == tuple(sorted(FUNDS.values()))
    assert wave.event_ids == tuple(sorted(sent))
    assert (wave.first_sent, wave.last_sent) == (WAVE, WAVE + timedelta(hours=4))


def test_the_wave_says_sent_replied_bounced_and_followed_up_each_as_a_measured_number(store):
    f15(store)
    [wave] = waves(store)
    assert (wave.sent.value, wave.sent.n, wave.sent.basis) == (5, 5, "wave")
    assert (wave.replied, wave.bounced, wave.followed_up) == ((COBALT,), (LATTICE,), (JUNIPER,))
    assert wave.reply_rate == rate_of(1, 5, basis="wave")
    assert wave.bounce_rate == rate_of(1, 5, basis="wave")
    assert wave.follow_up_rate == rate_of(1, 5, basis="wave")


def test_the_days_since_its_last_send_read_the_sweeps_clock(store):
    """56 days and 7 hours from the fifth send at 05:00 on 11 August to the sweep at noon on
    6 October — the LAST send, not the first (56 days 11 hours)."""
    f15(store)
    [wave] = waves(store)
    assert wave.days_since_last_send == 56.3


def test_nothing_after_the_sweeps_clock_is_seen(store):
    """A replay at the second hour sees three sends, no bounce yet (it came twenty seconds after
    the third), no answer and no follow-up — what the sweep at that instant could have seen."""
    f15(store)
    [wave] = waves(store, now=WAVE + timedelta(hours=2, seconds=10))
    assert wave.recipients == tuple(sorted((COBALT, JUNIPER, LATTICE)))
    assert (wave.replied, wave.bounced, wave.followed_up) == ((), (), ())
    assert wave.days_since_last_send == 0.0


# ── what makes a wave, and what does not ─────────────────────────────────────────────────────────

def test_two_subjects_are_two_waves(store):
    the_wave(store)
    the_wave(store, subject="Nimbus Labs - our August update", prefix="update",
             funds=tuple(FUNDS.items())[:3], start=WAVE + timedelta(hours=6))
    found = waves(store)
    assert sorted((w.line, w.sent.value) for w in found) == [
        ("Nimbus Labs - our August update", 3), (SUBJECT, 5)]
    assert len({w.wave_id for w in found}) == 2


def test_the_same_subject_to_two_addresses_is_no_wave_and_to_three_is_one(store):
    funds = tuple(FUNDS.items())
    the_wave(store, funds=funds[:2])
    assert waves(store) == ()
    the_wave(store, funds=funds[2:3], prefix="third", start=WAVE + timedelta(hours=3))
    [wave] = waves(store)
    assert wave.recipients == tuple(sorted((COBALT, JUNIPER, LATTICE)))


def test_a_send_eight_days_later_is_a_new_wave(store):
    funds = tuple(FUNDS.items())
    the_wave(store, funds=funds[:3])
    the_wave(store, funds=funds[2:], prefix="again", start=WAVE + timedelta(days=8))
    first, second = sorted(waves(store), key=lambda w: w.first_sent)
    assert first.recipients == tuple(sorted((COBALT, JUNIPER, LATTICE)))
    assert second.recipients == tuple(sorted((LATTICE, MERIDIAN, NORTHSTAR)))
    assert first.wave_id != second.wave_id
    assert first.followed_up == (LATTICE,), "the second wave wrote to Lattice again"


def test_a_send_seven_days_after_the_first_is_still_the_same_wave(store):
    """The window is seven days from the wave's FIRST send, inclusive: Meridian at exactly seven
    days joins it, Northstar a minute later does not."""
    the_wave(store, funds=tuple(FUNDS.items())[:3])
    send(store, "evt_day7", to=(MERIDIAN,), at=WAVE + timedelta(days=WAVE_WINDOW_DAYS))
    send(store, "evt_day7_late", to=(NORTHSTAR,),
         at=WAVE + timedelta(days=WAVE_WINDOW_DAYS, minutes=1))
    [wave] = waves(store)
    assert wave.recipients == tuple(sorted((COBALT, JUNIPER, LATTICE, MERIDIAN)))
    assert wave.last_sent == WAVE + timedelta(days=7)


def test_our_own_colleague_is_never_a_recipient(store):
    """Copied on the pitch, Priya — at the founder's own domain — is not an outside address: two
    funds and a colleague are no wave, and a third fund makes one without her."""
    send(store, "evt_a", to=(COBALT, COLLEAGUE), at=WAVE)
    send(store, "evt_b", to=(JUNIPER, COLLEAGUE), at=WAVE + timedelta(hours=1))
    assert waves(store) == ()
    send(store, "evt_c", to=(LATTICE, COLLEAGUE, FOUNDER), at=WAVE + timedelta(hours=2))
    [wave] = waves(store)
    assert wave.recipients == tuple(sorted((COBALT, JUNIPER, LATTICE)))


def test_a_reply_chain_in_the_subject_is_the_same_wave_and_adds_no_recipient(store):
    """Three days on we write to Meridian again under `Re: Fwd:` — the same subject, inside the
    window: still one wave of five, now with one follow-up and a later last send."""
    the_wave(store)
    send(store, "evt_again", to=(MERIDIAN,), subject=f"RE:  Fwd: {SUBJECT.upper()}",
         thread="t-to-4", at=WAVE + timedelta(days=3))
    [wave] = waves(store)
    assert wave.sent.value == 5
    assert wave.followed_up == (MERIDIAN,)
    assert "evt_again" in wave.event_ids
    assert wave.last_sent == WAVE + timedelta(days=3)


def test_a_send_with_no_prepared_text_has_no_subject_to_group_by(store):
    """An archive keeps no prepared text (STEP-03), and prepared text ages out at 180 days: with no
    subject the third send joins nothing, and two sends are no wave."""
    funds = tuple(FUNDS.items())
    the_wave(store, funds=funds[:2])
    send(store, "evt_archived", to=(LATTICE,), at=WAVE + timedelta(hours=2), prepared=False)
    assert waves(store) == ()


def test_a_send_captured_privately_is_no_part_of_a_wave(store):
    """An org-level reader: what a seat captured privately is no wave's send."""
    sent = the_wave(store, funds=tuple(FUNDS.items())[:3])
    private(store, sent[0])
    assert waves(store) == ()


def test_another_tenants_wave_is_never_this_ones(store):
    the_wave(store, org=OTHER)
    assert waves(store) == ()
    [wave] = waves(store, org=OTHER)
    assert wave.sent.value == 5


# ── replied, bounced, followed up ────────────────────────────────────────────────────────────────

def test_replied_is_their_own_mail_after_their_send(store):
    """Meridian's responder answered for it; Northstar wrote to us a week BEFORE the pitch; neither
    has replied. Northstar's own mail after the pitch is a reply."""
    the_wave(store)
    reply(store, "evt_ooo", sender=MERIDIAN, at=WAVE + timedelta(hours=3, minutes=1),
          responder=True)
    reply(store, "evt_before", sender=NORTHSTAR, at=WAVE - timedelta(days=7))
    [wave] = waves(store)
    assert wave.replied == ()
    reply(store, "evt_after", sender=NORTHSTAR, at=WAVE + timedelta(days=4))
    [wave] = waves(store)
    assert wave.replied == (NORTHSTAR,)
    assert wave.reply_rate == rate_of(1, 5, basis="wave")


def test_a_bounce_is_a_failure_reported_at_or_after_their_send(store):
    """Lattice's address bounced a month before this pitch — an older one — and that is not this
    wave's bounce. When it bounces again after the pitch it is, although the fact on the address
    still carries the first report's time: the second report only corroborates it."""
    bounce(store, "evt_old_bounce", address=LATTICE, at=WAVE - timedelta(days=30))
    the_wave(store)
    [wave] = waves(store)
    assert wave.bounced == ()
    bounce(store, "evt_new_bounce", address=LATTICE, thread="t-to-3",
           at=WAVE + timedelta(hours=2, seconds=20))
    [wave] = waves(store)
    assert wave.bounced == (LATTICE,)


def test_followed_up_is_a_later_send_to_them_and_never_their_first(store):
    """A send to Cobalt Peak before the wave is not a follow-up of it; the wave's own first sends
    are not either. Only a later one is."""
    send(store, "evt_earlier", to=(COBALT,), subject="Hello from Nimbus Labs",
         at=WAVE - timedelta(days=20))
    the_wave(store)
    [wave] = waves(store)
    assert wave.followed_up == ()
    send(store, "evt_later", to=(COBALT,), subject="Our deck, as promised",
         at=WAVE + timedelta(days=12))
    [wave] = waves(store)
    assert wave.followed_up == (COBALT,)


# ── the sentence first: today's campaign rule, unchanged ─────────────────────────────────────────

def test_a_sentence_campaign_is_a_wave_recognised_by_its_sentence(store):
    """Three sends under three different subjects, each carrying the sentence L1 qualified: one
    campaign, so one wave — with the campaign's own id, and the sentence as its line."""
    funds = tuple(FUNDS.items())[:3]
    for i, (name, fund) in enumerate(funds, start=1):
        at = WAVE + timedelta(minutes=10 * i)
        send(store, f"evt_s{i}", to=(fund,), subject=f"For {name}", thread=f"t-s-{i}", at=at)
        qualified(store, f"evt_s{i}", PITCH, at=at)
    with store.engine.connect() as c:
        [campaign] = find_campaigns(c, ORG, since=SINCE)
    [wave] = waves(store)
    assert wave.recognised_by == BY_SENTENCE
    assert wave.wave_id == campaign.campaign_id
    assert wave.line == PITCH
    assert wave.recipients == tuple(sorted((COBALT, JUNIPER, LATTICE)))
    assert wave.event_ids == campaign.event_ids
    assert waves(store, now=WAVE + timedelta(minutes=15)) == (), \
        "at a quarter past, one send of the three had gone"


def test_a_sentence_campaign_left_with_two_outside_people_is_no_wave(store):
    """Today's campaign rule counts every node our mail wrote `thread.last_outbound` on, and the
    pipeline writes it on a colleague at our declared domain (it skips exact addresses of ours
    only): three recipients to `find_campaigns`, unchanged — two outside people to a wave, so no
    wave, and the subject, left the same three sends, finds two as well."""
    for i, to in enumerate((COBALT, JUNIPER, COLLEAGUE), start=1):
        at = WAVE + timedelta(minutes=10 * i)
        send(store, f"evt_c{i}", to=(to,), thread=f"t-c-{i}", at=at)
        qualified(store, f"evt_c{i}", PITCH, at=at)
    with store.engine.connect() as c:
        [campaign] = find_campaigns(c, ORG, since=SINCE)
    assert campaign.size == 3
    assert waves(store) == ()


def test_a_send_already_in_a_sentence_wave_is_never_counted_again_by_its_subject(store):
    """One subject AND one qualified sentence: the sentence recognises the wave first, and the same
    sends make no second wave by their subject."""
    sent = the_wave(store, funds=tuple(FUNDS.items())[:3])
    for i, event_id in enumerate(sent):
        qualified(store, event_id, PITCH, at=WAVE + timedelta(hours=i))
    [wave] = waves(store)
    assert wave.recognised_by == BY_SENTENCE


# ── the subject: Layer 1's, compared without case, whitespace or a reply chain ──────────────────

def test_the_subject_is_the_one_layer_1_wrote_at_the_head_of_the_prepared_text():
    assert subject_of(_prepared(SUBJECT, BODY.format(name="Cobalt Peak"))) == SUBJECT


def test_a_mail_whose_prepared_text_has_no_blank_line_has_no_subject():
    """Layer 1 writes the subject and a blank line before the body; with no blank line there is no
    subject to read — a one-paragraph mail sent without one."""
    assert subject_of(_prepared("", "Sharing our deck ahead of Thursday, thanks.")) is None
    assert subject_of(None) is None


def test_the_subject_is_compared_without_case_whitespace_or_a_reply_chain():
    assert normalise_subject(f"  RE:  fwd: Re:{SUBJECT.upper()}  ") == normalise_subject(SUBJECT)
    assert normalise_subject(f"Fw: {SUBJECT}") == SUBJECT.lower()
    assert normalise_subject("Nimbus   Labs\t-  raising") == "nimbus labs - raising"
    assert normalise_subject("Review: our seed round") == "review: our seed round"
    assert normalise_subject("Re: Re:") == ""

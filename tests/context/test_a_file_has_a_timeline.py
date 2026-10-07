"""STEP-10 · a file has a timeline — every touch both ways, who did it, its evidence, the gaps, and
whether the silence now is longer than any before it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_has_a_timeline.py -q

`context/workstream_timeline.timeline_for` (tree `yc2_w27_s10 · M29.C2.L-logic.V2.U01`). Measured
(`STEP-10` §8.2): the directed timeline existed only inside `context/waiting`, rebuilt over 180 days and
reduced to four "last seen" facts; `timeline_unit` reads `timeline.events`, which nothing writes, so it
saw one event; calendar touches were in no timeline at all. A file (STEP-09) is one anchor's
correlations, so its timeline is their members, read: each mail in or out with who WROTE it — the
event's actor, so an introduction is the connector's touch, not the person's (`STEP-10` N3) — and each
meeting once, at its current start, never a cancelled one; a meeting still to come is listed as
booked and is not a touch. The gaps between touches, the usual one as a `Measured` with its n, and
whether the open silence outlasts the longest gap the file ever closed (`timeline_unit`'s
`silence_exceeds_prior_gaps`). An org-level reader: nothing a seat captured privately.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.structured import commit_structured
from genios_engine.context.workstream_timeline import timeline_for
from genios_engine.contracts.measured import Measured
from genios_engine.platform.self_identity import identity_for

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, brief, mention, node,
                               process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s10_file_timeline"
OTHER = "org_s10_file_timeline_other"
PRIYA = "priya@northwind.test"
RAHUL = "rahul@kestrelcap.test"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    tenant(pg_store, OTHER)
    yield pg_store
    reset(pg_store, ORG)
    reset(pg_store, OTHER)


def _meeting(store, event_id: str, *, meeting: str, start, attendees=(PRIYA, FOUNDER),
             organizer: str = FOUNDER, status: str = "confirmed", captured=None,
             org: str = ORG) -> None:
    """One version of a calendar event, as the drain lands it: its ledger row at the meeting's
    start (`capture/connectors/calendar._to_raw`), then the structured lane (`context/structured`)."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, recipients, occurred_at, captured_at, outcome) "
            "values (:e, :o, 'con_cal', 'gcal', 'calendar_event', :m, :k, cast(:a as jsonb), :r, "
            "        :at, :cap, 'emitted')"),
            {"e": event_id, "o": org, "m": meeting, "k": f"gcal:calendar_event:{event_id}",
             "a": json.dumps({"type": "external_contact", "email": organizer}),
             "r": list(attendees), "at": start, "cap": captured or start})
    us = identity_for(store, org)
    commit_structured(
        store, org_id=org, event_id=event_id, source="gcal", source_object_id=meeting,
        structured_fields={"meeting.title": "Northwind x Nimbus", "meeting.status": status,
                           "meeting.start_at": start.isoformat()},
        node_type="meeting", occurred_at=start, version_at=captured or start,
        display_name="Northwind x Nimbus",
        relations=[{"node_type": "person", "canonical_key": a, "edge_type": "attended",
                    "direction": "in"} for a in attendees],
        internal_emails=us.addresses, self_identity=us)


def _priya(store, org: str = ORG) -> None:
    """Priya writes; we answer two days later; she writes again three days after that; a call four
    days on; we write three days after the call. Gaps 2, 3, 4, 3."""
    process(store, org, event_id=f"{org}_in_1", sender=PRIYA, thread="t_np", at=T0)
    process(store, org, event_id=f"{org}_out_1", sender=FOUNDER, recipients=(PRIYA,),
            thread="t_np", at=T0 + timedelta(days=2))
    process(store, org, event_id=f"{org}_in_2", sender=PRIYA, thread="t_np",
            at=T0 + timedelta(days=5))
    _meeting(store, f"{org}_call_1", meeting=f"{org}_call", start=T0 + timedelta(days=9), org=org)
    process(store, org, event_id=f"{org}_out_2", sender=FOUNDER, recipients=(PRIYA,),
            thread="t_np", at=T0 + timedelta(days=12))


def _file(store, key: str, org: str = ORG) -> str:
    """The one file this sender's mail is in."""
    [file_id] = _anchors_of(store, key, org)
    return file_id


def _anchors_of(store, key: str, org: str) -> set[str]:
    with store.engine.connect() as c:
        return {r.anchor_node_id for r in c.execute(text(
            "select distinct k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id "
            "       and m.correlation_id = k.correlation_id "
            "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            " where k.org_id = :o and lower(se.actor->>'email') = :k"), {"o": org, "k": key})}


def _when(touches):
    return [((t.at - T0).total_seconds() / 86400, t.kind, t.direction, t.who, t.event_id)
            for t in touches]


def test_every_touch_both_ways_in_order_with_who_and_its_evidence(store):
    _priya(store)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=40))
    assert _when(tl.touches) == [
        (0.0, "mail", "in", PRIYA, f"{ORG}_in_1"),
        (2.0, "mail", "out", FOUNDER, f"{ORG}_out_1"),
        (5.0, "mail", "in", PRIYA, f"{ORG}_in_2"),
        (9.0, "meeting", "meeting", FOUNDER, f"{ORG}_call_1"),
        (12.0, "mail", "out", FOUNDER, f"{ORG}_out_2")]
    assert {t.thread for t in tl.touches if t.kind == "mail"} == {"t_np"}
    assert [t.mailbox for t in tl.touches] == ["con_x", "con_x", "con_x", "con_cal", "con_x"], (
        "each touch names the connection it came through")


def test_the_gaps_and_the_usual_gap_say_their_n(store):
    _priya(store)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=40))
    assert tl.gaps_days == (2.0, 3.0, 4.0, 3.0)
    assert tl.usual_gap == Measured(value=3.0, n=4, basis="file", unit="days")
    assert tl.usual_gap.sparse, "four gaps are too few to call a rhythm"
    assert tl.longest_gap_days == 4.0
    assert tl.days_quiet == 28.0
    assert tl.silence_exceeds_prior_gaps is True


def test_a_silence_inside_the_files_own_rhythm_is_not_a_finding(store):
    _priya(store)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=15))
    assert tl.days_quiet == 3.0
    assert tl.silence_exceeds_prior_gaps is False


def test_one_touch_has_no_gap_to_compare(store):
    process(store, ORG, event_id="evt_once", sender=PRIYA, thread="t_once", at=T0)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=30))
    assert [t.event_id for t in tl.touches] == ["evt_once"]
    assert tl.gaps_days == ()
    assert tl.usual_gap == Measured(value=None, n=0, basis="file", unit="days")
    assert tl.longest_gap_days is None
    assert tl.days_quiet == 30.0
    assert tl.silence_exceeds_prior_gaps is None, "nothing to compare is not a finding either way"


def test_an_introduction_is_the_connectors_touch_not_theirs(store):
    """Introly introduced Rahul; he answered a day later. The file's first touch is Introly's."""
    process(store, ORG, event_id="evt_intro", sender=CONNECTOR, sender_name="Introly",
            recipients=(FOUNDER, RAHUL), thread="t_intro", headers=UNSUBSCRIBE,
            mentions=(mention("Rahul Menon"),), company_brief=brief(ORG), at=T0)
    process(store, ORG, event_id="evt_rahul", sender=RAHUL, thread="t_intro",
            company_brief=brief(ORG), at=T0 + timedelta(days=1))
    [file_id] = _anchors_of(store, RAHUL, ORG)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, file_id, now=T0 + timedelta(days=3))
    assert [(t.direction, t.who, t.event_id) for t in tl.touches] == [
        ("in", CONNECTOR, "evt_intro"), ("in", RAHUL, "evt_rahul")]


def test_a_meeting_is_one_touch_at_its_current_start(store):
    """Moved from day 9 to day 10: two versions, one meeting, at the newer start."""
    process(store, ORG, event_id="evt_ask", sender=PRIYA, thread="t_np", at=T0)
    _meeting(store, "evt_call_v1", meeting="call_moved", start=T0 + timedelta(days=9),
             captured=T0 + timedelta(days=1))
    _meeting(store, "evt_call_v2", meeting="call_moved", start=T0 + timedelta(days=10),
             captured=T0 + timedelta(days=2))
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=20))
    assert _when(tl.touches) == [(0.0, "mail", "in", PRIYA, "evt_ask"),
                                 (10.0, "meeting", "meeting", FOUNDER, "evt_call_v2")]


def test_a_cancelled_meeting_is_no_touch(store):
    process(store, ORG, event_id="evt_ask", sender=PRIYA, thread="t_np", at=T0)
    _meeting(store, "evt_call_v1", meeting="call_off", start=T0 + timedelta(days=9),
             captured=T0 + timedelta(days=1))
    _meeting(store, "evt_call_v2", meeting="call_off", start=T0 + timedelta(days=9),
             status="cancelled", captured=T0 + timedelta(days=2))
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=20))
    assert [t.event_id for t in tl.touches] == ["evt_ask"]
    assert tl.upcoming == ()


def test_a_booked_meeting_is_upcoming_not_a_touch(store):
    _priya(store)
    _meeting(store, "evt_later_call", meeting="later_call", start=T0 + timedelta(days=60),
             captured=T0 + timedelta(days=29))
    _meeting(store, "evt_next_call", meeting="next_call", start=T0 + timedelta(days=45),
             captured=T0 + timedelta(days=30))
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=40))
    assert [t.event_id for t in tl.upcoming] == ["evt_next_call", "evt_later_call"], "soonest first"
    assert not {"evt_next_call", "evt_later_call"} & {t.event_id for t in tl.touches}
    assert tl.days_quiet == 28.0, "a call still to come does not end the silence"


def test_a_private_event_is_no_files_evidence(store):
    _priya(store)
    with store.engine.begin() as c:
        c.execute(text("update source_events set visibility_scope = 'private' "
                       " where org_id = :o and event_id = :e"), {"o": ORG, "e": f"{ORG}_out_2"})
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=40))
    assert f"{ORG}_out_2" not in [t.event_id for t in tl.touches]
    assert tl.days_quiet == 31.0


def test_another_tenants_file_shows_nothing_here(store):
    _priya(store, OTHER)
    theirs = _file(store, PRIYA, OTHER)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, theirs, now=T0 + timedelta(days=40))
    assert tl.touches == () and tl.upcoming == ()
    assert node(store, ORG, PRIYA) is None


def test_a_meeting_restored_after_a_cancel_is_a_touch_again(store):
    process(store, ORG, event_id="evt_ask", sender=PRIYA, thread="t_np", at=T0)
    for i, status in enumerate(("confirmed", "cancelled", "confirmed")):
        _meeting(store, f"evt_call_v{i}", meeting="call_back_on", start=T0 + timedelta(days=9),
                 status=status, captured=T0 + timedelta(days=1 + i))
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=20))
    assert [t.event_id for t in tl.touches] == ["evt_ask", "evt_call_v2"]


def test_another_tenants_cancel_does_not_cancel_our_meeting(store):
    """One Google event, on two tenants' calendars: their cancel is not ours."""
    process(store, ORG, event_id="evt_ask", sender=PRIYA, thread="t_np", at=T0)
    _meeting(store, "evt_ours", meeting="shared_call", start=T0 + timedelta(days=9))
    process(store, OTHER, event_id="evt_their_ask", sender=PRIYA, thread="t_np", at=T0)
    _meeting(store, "evt_theirs", meeting="shared_call", start=T0 + timedelta(days=9),
             status="cancelled", org=OTHER)
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=20))
    assert [t.event_id for t in tl.touches] == ["evt_ask", "evt_ours"]


def test_the_timeline_reads_as_json(store):
    from genios_engine.context.workstream_timeline import as_dict
    _priya(store)
    _meeting(store, "evt_next_call", meeting="next_call", start=T0 + timedelta(days=45),
             captured=T0 + timedelta(days=30))
    with store.engine.connect() as c:
        body = as_dict(timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=40)))
    assert body["touches"][0] == {"at": T0.isoformat(), "kind": "mail", "direction": "in",
                                  "who": PRIYA, "who_name": None,
                                  "event_id": f"{ORG}_in_1", "thread": "t_np",
                                  "mailbox": "con_x"}
    assert [t["event_id"] for t in body["upcoming"]] == ["evt_next_call"]
    assert body["gaps_days"] == [2.0, 3.0, 4.0, 3.0]
    assert body["usual_gap"] == Measured(value=3.0, n=4, basis="file", unit="days").as_dict()
    assert (body["longest_gap_days"], body["days_quiet"],
            body["silence_exceeds_prior_gaps"]) == (4.0, 28.0, True)
    assert (body["file_id"], body["as_of"]) == (_file(store, PRIYA),
                                                (T0 + timedelta(days=40)).isoformat())


def test_other_evidence_in_the_file_is_not_a_touch(store):
    """A screen capture filed with Priya is the file's evidence, not Priya or us writing."""
    _priya(store)
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, outcome) values ('evt_screen', :o, "
            " 'con_screen', 'screen_session', 'screen_capture', 'scr1', 'screen:scr1', "
            " cast(:a as jsonb), :at, 'emitted')"),
            {"o": ORG, "a": json.dumps({"type": "internal_user", "email": FOUNDER}),
             "at": T0 + timedelta(days=20)})
        c.execute(text(
            "insert into context_correlation_members (org_id, correlation_id, event_id) "
            "select org_id, correlation_id, 'evt_screen' from context_correlation_members "
            " where org_id = :o and event_id = :e"), {"o": ORG, "e": f"{ORG}_in_1"})
    with store.engine.connect() as c:
        tl = timeline_for(c, ORG, _file(store, PRIYA), now=T0 + timedelta(days=40))
    assert "evt_screen" not in [t.event_id for t in tl.touches + tl.upcoming]
    assert tl.days_quiet == 28.0

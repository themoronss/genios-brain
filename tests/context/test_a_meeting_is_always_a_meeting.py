"""STEP-05 · a calendar event is always a meeting — with its organizer, the newest version winning,
and never anchored on one of us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_meeting_is_always_a_meeting.py -q

Tree `yc2_w27_s05 · M23.C3.L-logic.V2.U04`. A calendar event used to reach memory only while its
deadline signal was alive, so production held 2 of 34 meetings. Now every version drains (C2, C3.U03):
each edit is its own event, captured with the meeting's START as its time. The structured lane filed
every fact at that time, so a meeting moved EARLIER lost to its own old version — the newer statement
looked older — in whichever order the two drained. A meeting's facts now carry when the calendar said
them (`updated`), as `_commit_availability` already did for a leave block; and a meeting keeps its
organizer. And the correlation it joins leaves out every one of us the identity knows — a colleague
at a declared domain too, which the address list missed (`03` F70).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import runner
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import encrypt

pytestmark = pytest.mark.pg

ORG = "a_meeting_is_always_a_meeting_org"
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
FOUNDER, OURS, COLLEAGUE = "founder.cal@gmail.com", "kitebird.test", "ops@kitebird.test"
NEEL, THEIRS = "neel@insight.test", "insight.test"
MEETING = "gcal_insight_intro"


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        for tbl in ("context_correlation_members", "context_situations", "context_correlations"):
            c.execute(text(f"delete from {tbl} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Meera Iyer', :e)"),
                  {"o": ORG, "e": FOUNDER})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'domain', :d, 'test')"), {"o": ORG, "d": OURS})
    yield pg_store
    _reset(pg_store)


def _version(c, event_id: str, *, start: str, updated: str, summary: str,
             attendees=(NEEL, FOUNDER), organizer: str = NEEL) -> None:
    """One edit of the meeting, landed as the calendar connector lands it: its own event, the
    meeting's start as its time, `updated` in the payload (`capture/connectors/calendar._to_raw`)."""
    raw = {"summary": summary, "start": start,
           "end": (datetime.fromisoformat(start) + timedelta(minutes=30)).isoformat(),
           "status": "confirmed", "attendees": list(attendees), "organizer": organizer,
           "updated": updated}
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, recipients, occurred_at, outcome) values "
        "(:e, :o, 'conn_cal', 'gcal', 'calendar_event', :m, :e, cast(:a as jsonb), :r, :at, "
        "'emitted')"),
        {"e": event_id, "o": ORG, "m": MEETING, "r": list(attendees),
         "a": json.dumps({"type": "external_contact", "email": organizer}),
         "at": datetime.fromisoformat(start)})
    c.execute(text(
        "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
        "values (:id, :o, :e, 'application/json', :enc, :exp)"),
        {"id": f"pay_{event_id}", "o": ORG, "e": event_id,
         "enc": encrypt(json.dumps(raw), get_settings().crypto_key),
         "exp": NOW + timedelta(days=180)})


def _drain(store) -> dict:
    return runner.process_pending(org_id=ORG, store=store, llm=None,
                                  crypto_key=get_settings().crypto_key, eval_time=NOW)


def _facts(store, *, status: str = "active") -> dict[str, list]:
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select f.field, f.value #>> '{}' as value from graph_facts f "
            "  join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
            "       and n.valid_to is null "
            " where f.org_id = :o and n.canonical_key = :k and f.status = :s "
            "   and (f.valid_to is null or :s = 'historical')"),
            {"o": ORG, "k": f"gcal:{MEETING}", "s": status}).fetchall()
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r.field, []).append(r.value)
    return out


V1 = dict(start="2026-10-20T10:00:00+05:30", updated="2026-10-01T09:00:00Z",
          summary="Insight intro call")
V2 = dict(start="2026-10-15T10:00:00+05:30", updated="2026-10-05T09:00:00Z",
          summary="Insight intro call (moved)")


def test_a_meeting_with_no_signal_keeps_its_organizer(store):
    with store.engine.begin() as c:
        _version(c, "cal_v1", **V1)
    assert _drain(store)["outcomes"] == {"committed_structured": 1}
    facts = _facts(store)
    assert facts["meeting.organizer"] == [NEEL]
    assert facts["meeting.title"] == [V1["summary"]]


def test_a_meeting_moved_earlier_shows_its_new_time(store):
    """Both edits drain in one sweep, in whatever order: the newer statement wins."""
    with store.engine.begin() as c:
        _version(c, "cal_v1", **V1)
        _version(c, "cal_v2", **V2)
    _drain(store)
    facts = _facts(store)
    assert facts["meeting.start_at"] == [V2["start"]], facts
    assert facts["meeting.title"] == [V2["summary"]]


def test_an_older_edit_drained_later_never_overwrites_a_newer_one(store):
    with store.engine.begin() as c:
        _version(c, "cal_v2", **V2)
    _drain(store)
    with store.engine.begin() as c:                 # the older edit arrives after (a re-delivery)
        _version(c, "cal_v1", **V1)
    _drain(store)
    assert _facts(store)["meeting.start_at"] == [V2["start"]]
    assert V1["start"] in _facts(store, status="historical")["meeting.start_at"], (
        "the older edit was not kept as history")


def test_a_colleague_at_our_declared_domain_never_anchors_a_meeting(store):
    """`03` F70: the correlation left out our exact addresses only. Our company and the outside one
    both exist, so the lift could reach either."""
    with store.engine.begin() as c:
        for domain in (OURS, THEIRS):
            store.find_or_create_node(c, org_id=ORG, node_type="company", canonical_key=domain,
                                      display_name=domain, event_id="seed")
        _version(c, "cal_team", **V1, attendees=(NEEL, FOUNDER, COLLEAGUE))
    _drain(store)
    with store.engine.connect() as c:
        anchors = {r.canonical_key for r in c.execute(text(
            "select n.canonical_key from context_correlation_members m "
            "  join context_correlations k on k.org_id = m.org_id "
            "       and k.correlation_id = m.correlation_id "
            "  join graph_nodes n on n.org_id = k.org_id and n.node_id = k.anchor_node_id "
            "       and n.valid_to is null "
            " where m.org_id = :o and m.event_id = 'cal_team'"), {"o": ORG})}
    assert OURS not in anchors and COLLEAGUE not in anchors, sorted(anchors)
    assert THEIRS in anchors, sorted(anchors)

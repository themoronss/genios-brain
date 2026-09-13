"""P5 group B — the pure halves: prep compose / retime / lead, follow-up compose, transcript row
normalisation, the contract field and the post-pass registration. `tests/test_meetings_pg.py`
runs the SQL and the route."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.contracts.moments import EvaluateRequest
from genios_engine.reason.meetings import passes as MS
from genios_engine.reason.meetings import prep as MP
from genios_engine.reason.team import postpass

NOW = datetime(2026, 9, 17, 5, 0, tzinfo=timezone.utc)
START = NOW + timedelta(minutes=15)


def _f(value):
    return (value, NOW - timedelta(days=1))


def _read() -> MP.PrepRead:
    att = MP.Attendance(meeting_node_id="mtg", me="me", attendees=("priya", "ravi", "anon"),
                        names={"priya": "Priya Shah", "ravi": "Ravi Kumar", "anon": None,
                               "me": "Founder"},
                        title="Acme review", start_at=START, end_at=START + timedelta(hours=1))
    r = MP.PrepRead(att=att)
    r.nodes = {"acme": ("company", "Acme Logistics"), "deal": ("deal", None),
               "c1": ("commitment", "send the signed SOW"), "c2": ("commitment", "x"),
               "c3": ("commitment", "share the pricing deck"), "c4": ("commitment", "leak"),
               "c5": ("commitment", "confirm the pilot scope")}
    r.employer = {"priya": "acme"}
    r.company_deal = {"acme": "deal"}
    r.theirs = {"priya": ["c1", "c2", "c4"]}
    r.mine = ["c3"]
    r.facts = {
        "priya": {"person.title": _f("VP Ops")},
        "deal": {"deal.stage": _f("negotiation")},
        "c1": {"commitment.text": _f("send the signed SOW"), "commitment.status": _f("open"),
               "commitment.due_at": _f((NOW - timedelta(days=2)).isoformat())},
        "c2": {"commitment.text": _f("old promise"), "commitment.status": _f("done")},
        "c3": {"commitment.text": _f("share the pricing deck"), "commitment.status": _f("open"),
               "commitment.owed_to": _f("Ravi Kumar")},
        # c4: no READABLE text (another seat's private overlay was filtered out) → never shown,
        # and never through its node display name
        "c4": {"commitment.status": _f("open")},
        "c5": {"commitment.text": _f("confirm the pilot scope"), "commitment.status": _f("open")},
    }
    r.last_touch = {"priya": NOW - timedelta(days=3)}
    r.prior = ("prev", "Acme kickoff", NOW - timedelta(days=7))
    r.prior_items = ["c5", "c1"]
    r.changes = [{"node_id": "deal", "field": "deal.stage", "old": "proposal",
                  "new": "negotiation", "changed_at": "2026-09-16T00:00:00Z"}]
    return r


def test_prep_lists_open_loops_per_attendee_in_four_lines():
    out = MP.compose(_read(), now=NOW)
    assert out["capability_id"] == "moment.meeting_prep" and out["priority"] == "high"
    assert out["kind"] == "advice"
    assert out["headline"] == "Acme review in 15 min — 3 open loops with Priya +1"
    lines = out["body"].split("\n")
    assert len(lines) <= 4
    assert lines[0] == ("Priya Shah (VP Ops, Acme Logistics) · last touch 3 d ago · "
                        "They owe: send the signed SOW (overdue since 15 Sep) · Deal: negotiation")
    assert lines[1] == "Ravi Kumar · You owe: share the pricing deck"
    # c1 is already on Priya's line; only the rest of the last meeting's open items
    assert lines[2] == "Still open from Acme kickoff (10 Sep): confirm the pilot scope"
    assert lines[3] == "Changed: Acme Logistics deal stage proposal → negotiation"
    assert "leak" not in out["body"] and "old promise" not in out["body"]
    assert out["actions"] == [{"id": "open_meeting",
                               "payload": {"meeting_node_id": "mtg", "url": None}}]
    assert out["ttl_seconds"] == 25 * 60
    assert out["evidence"][0] == {"node_id": "mtg", "field": "meeting.start_at",
                                  "source": "graph", "at": "2026-09-17T05:15:00Z"}


def test_prep_is_silent_with_nothing_to_say():
    att = MP.Attendance(meeting_node_id="m", me="me", attendees=(), title="Solo",
                        start_at=START)
    assert MP.compose(MP.PrepRead(att=att), now=NOW) is None


def test_lead_ttl_live_and_retime():
    assert MP.lead("X", NOW + timedelta(minutes=14, seconds=10), NOW) == "X in 15 min"
    assert MP.lead("X", NOW + timedelta(minutes=80), NOW) == "X in 1 h 20 min"
    assert MP.lead("X", NOW + timedelta(hours=2), NOW) == "X in 2 h"
    assert MP.lead("X", NOW, NOW) == "X now"
    assert MP.lead("X", NOW - timedelta(minutes=4), NOW) == "X started 4 min ago"
    assert MP.ttl_for(NOW - timedelta(minutes=9, seconds=30), NOW) == 60
    att = MP.Attendance(meeting_node_id="m", me="me", attendees=(), start_at=START)
    assert MP.live(att, NOW) and not MP.live(att, START + timedelta(minutes=10))
    assert not MP.live(None, NOW)
    cached = {**MP.compose(_read(), now=NOW - timedelta(hours=2)), "displayed": False}
    assert cached["headline"].startswith("Acme review in 2 h 15 min")
    again = MP.retime(cached, NOW)
    assert again["headline"] == "Acme review in 15 min — 3 open loops with Priya +1"
    assert again["ttl_seconds"] == 25 * 60 and again["body"] == cached["body"]
    assert MP.retime(cached, START + timedelta(minutes=11)) is None
    assert MP.retime({"headline": "no meta"}, NOW) is None


def test_contract_field_and_post_pass_registration():
    req = EvaluateRequest(moment_request_id="r1", features={"meeting_node_id": "node_m"})
    assert req.features.meeting_node_id == "node_m"
    assert EvaluateRequest(moment_request_id="r2").features.meeting_node_id is None
    assert ("meetings", "genios_engine.reason.meetings.passes") in postpass.PASSES
    assert postpass._present("genios_engine.reason.meetings.passes")


def test_transcript_row_columns_or_document():
    cols = MS.transcript_of({"transcript_id": "t1", "principals": ["A@x.test", "b@x.test"],
                             "meeting": {"meeting_node_id": "m1", "title": "Sync"},
                             "updated_at": NOW.replace(tzinfo=None)})
    assert cols.meeting_node_id == "m1" and cols.title == "Sync"
    assert cols.principals == ("a@x.test", "b@x.test") and cols.updated_at == NOW
    doc = MS.transcript_of({"id": 7, "transcript": '{"transcript_id": "t2", "principals": '
                                                   '["c@x.test"], "meeting": '
                                                   '{"meeting_node_id": null}}'})
    assert doc.transcript_id == "t2" and doc.principals == ("c@x.test",)
    assert doc.meeting_node_id is None
    assert MS.transcript_of({"status": "extracted"}) is None


def _items() -> MS.Items:
    A, B = "a@x.test", "b@x.test"
    org, priv_b = (None, None), ("private", [B])
    return MS.Items(
        nodes={"c1": ("commitment", [org]), "c2": ("commitment", [org]),
               "c3": ("commitment", [priv_b]), "d1": ("decision", [org]),
               "c4": ("commitment", [org])},
        facts=[("c1", "commitment.text", "send the ISO pack", "org", None),
               ("c1", "commitment.due_at", "2026-09-20T00:00:00Z", "org", None),
               ("c2", "commitment.text", "confirm the audit date", "org", None),
               ("c3", "commitment.text", "SECRET scope", "private", [B]),
               ("c4", "commitment.text", "private words", "private", [B]),
               ("c4", "commitment.text", "book the auditor", "org", None),
               ("d1", "decision.text", "go with Vendor X", "org", None)],
        owners=[("c1", "pa", "Aarav Mehta", {A}, None, None),
                ("c2", "pp", "Priya Shah", {"priya@acme.test"}, None, None),
                ("c3", "pp", "Priya Shah", {"priya@acme.test"}, "private", [B])])


def test_followup_body_per_seat_visibility():
    a = MS.compose_followup(_items(), viewer="a@x.test", title="ISO audit", meeting_node_id="m")
    assert a["headline"] == "Follow-ups from ISO audit — 1 for you"
    assert a["body"] == ("You: send the ISO pack (due 20 Sep) · Priya: confirm the audit date · "
                         "No owner: book the auditor · Decided: go with Vendor X")
    assert "SECRET" not in a["body"] and "private words" not in a["body"]
    assert "c3" not in a["subjects"] and a["subjects"][0] == "m"
    b = MS.compose_followup(_items(), viewer="b@x.test", title="ISO audit", meeting_node_id="m")
    assert "Aarav: send the ISO pack" in b["body"] and "SECRET scope" in b["body"]
    assert "private words" in b["body"] and b["headline"] == "Follow-ups from ISO audit"
    only_private = MS.Items(nodes={"c3": ("commitment", [("private", ["b@x.test"])])},
                            facts=[], owners=[])
    assert MS.compose_followup(only_private, viewer="a@x.test", title=None,
                               meeting_node_id=None) is None

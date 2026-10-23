"""Every card reader reads the one live-card fragment — GeniOS-011 S36.U2.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_live_card_reaches_every_reader_pg.py

`surfaces-question-and-team-cards-reach-only-the-cards-page` (+ `l4-morning-brief-unreached`): the Cards queue
had three doors — the decision's authority, the P4 situation door, the question door (`deliver/store.queue`) —
and every other reader joined the decision's alone. So a question card and a meeting follow-up (a situation card)
were on the Cards page and nowhere else: not on Home "Today" (the morning brief), not on the Context panel, not
on `/v1/insights`, not in the MCP `list_cards` tool, not in Ask's recall.

Each reader now reads `deliver/store.LIVE_CARD_FROM`. Driven here through REAL writers — the P-16 pass over a real
transcript (the follow-up) and STEP-13's question door (the question) — and read back through each reader's own
function. The push lanes and the agent poll they mirror read `PUSH_CARD_FROM` — the decision door only, declared
by `PUSH_CARD_DOORS` — and the same two cards are asserted NOT to reach them.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from tests.deliver.test_a_question_card_has_its_door import _asked
from tests.deliver.test_a_question_card_has_its_door import _card
from tests.deliver.test_a_question_card_has_its_door import _insert
from tests.deliver.test_a_question_card_has_its_door import cards  # noqa: F401 — a fixture
from tests.reason.expert.test_a_covered_file_decides_once import world  # noqa: F401 — a fixture
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401 — a fixture
from tests.test_a_meeting_followup_card_opens_pg import _a_meeting_raised_one_item
from tests.test_a_meeting_followup_card_opens_pg import _clock  # noqa: F401 — an autouse fixture
from tests.test_a_meeting_followup_card_opens_pg import _founder
from tests.test_a_meeting_followup_card_opens_pg import _the_followup_card
from tests.test_a_meeting_followup_card_opens_pg import client  # noqa: F401 — a fixture

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


def _followup(client) -> dict:
    """A P-16 follow-up card, emitted by the real pass for a registered founder."""
    import tests.test_a_meeting_followup_card_opens_pg as U1
    from genios_engine.reason.meetings import passes as MS
    founder = _founder(client)
    org = founder["org_id"]
    _a_meeting_raised_one_item(org, founder["email"], founder["uid"])
    assert MS.emit_followups(_engine(), None, org, now=U1.NOW) == 1
    card = _the_followup_card(org)
    return {"org": org, "seat": founder["seat_id"], "card_id": card["card_id"],
            "capability": card["capability_id"], **_subject_of(org, card["card_id"])}


def _question(world, cards_store) -> dict:
    """A STEP-13 question card through its own door. The world's clock is a fixed date (2026-08-20); the
    readers here read the wall clock, so the question's signal and card are moved to a live expiry — the one
    clause of the question's authority that is a time."""
    _store, org, _anchor, signal, question, bound = _asked(world)
    card_id, created, _ = _insert(cards_store, _card(org, signal, question, bound))
    assert created and card_id
    with _engine().begin() as c:
        c.execute(text("update signals set authority_expires_at = now() + interval '1 day' "
                       "where org_id = :o and signal_id = :s"), {"o": org, "s": signal.signal_id})
        c.execute(text("update cards set expires_at = now() + interval '1 day' "
                       "where org_id = :o and card_id = :k"), {"o": org, "k": card_id})
    return {"org": org, "seat": None, "card_id": card_id, "capability": "expert.file_review",
            **_subject_of(org, card_id)}


def _subject_of(org: str, card_id: str) -> dict:
    with _engine().connect() as c:
        r = c.execute(text(
            "select s.subject_node_id, n.node_type, n.display_name from cards k join signals s "
            "on s.signal_id = k.signal_id and s.org_id = k.org_id left join graph_nodes n "
            "on n.org_id = k.org_id and n.node_id = s.subject_node_id and n.valid_to is null "
            "where k.org_id = :o and k.card_id = :k"), {"o": org, "k": card_id}).one()
    return {"subject": r.subject_node_id, "subject_type": r.node_type, "subject_name": r.display_name}


def _cards_queue_has_it(live: dict) -> None:
    """The premise: the Cards queue (the doors' own reader) shows the card."""
    from genios_engine.deliver.store import CardStore
    queued = [r["card_id"] for r in CardStore(URL).queue(live["org"], admin=True, record_impressions=False)]
    assert live["card_id"] in queued, queued


def _person_readers_show_it(live: dict, monkeypatch) -> None:
    from genios_engine.api import intelligence_routes as IR
    from genios_engine.api import workspace_routes as WR
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.deliver.store import live_cards_about
    from genios_engine.mcp import server as MCP
    from genios_engine.platform.auth import AuthCtx
    from genios_engine.platform.self_identity import SelfIdentity
    from genios_engine.reason.moments import recall as R
    org, card_id = live["org"], live["card_id"]
    graph = GraphStore(URL)
    monkeypatch.setattr(WR, "_store", lambda: graph)
    monkeypatch.setattr(IR, "_graph", graph)

    # Home "Today" — the morning brief the dashboard reads (`/api/org/{org}/morning-brief`)
    brief = WR.build_morning_brief(org)
    assert card_id in [p["card_id"] for p in brief["priorities"]], brief
    if live["seat"]:
        seat_brief = WR.build_morning_brief(org, seat_id=live["seat"])
        assert card_id in [p["card_id"] for p in seat_brief["priorities"]], "the seat's own brief too"

    # the Context page's entity panel
    assert live["subject_name"], "the card's subject is a graph node the panel can resolve"
    panel = WR.context_bundle(org, WR.ContextLookup(entity_name=live["subject_name"]), org=org)
    assert card_id in [d["card_id"] for d in panel["decisions"]], panel["decisions"]

    # GET /v1/insights (the extension feed; G6's goal board)
    feed = IR.list_insights(limit=50, state="open", ctx=AuthCtx(org_id=org))
    assert card_id in [i["id"] for i in feed["insights"]], feed

    # MCP list_cards for a person's session (no agent identity)
    assert card_id in [r["card_id"] for r in MCP._session_cards(graph.engine, org)]

    # Ask's moment recall: the live cards about the subject ground it
    from datetime import datetime, timezone
    with graph.engine.connect() as c:
        read = R.read(c, org_id=org, subject=R.Subject(node_id=live["subject"],
                                                        node_type=live["subject_type"] or "person",
                                                        name=live["subject_name"]),
                      me=None, viewer=None, us=SelfIdentity(), now=datetime.now(timezone.utc),
                      live_cards=live_cards_about)
    assert live["capability"] in [s["rule_id"] for s in read.signals], read.signals


def _push_readers_do_not(live: dict) -> None:
    """`PUSH_CARD_DOORS` is the decision door alone: no push lane, and not the agent poll push mirrors."""
    from datetime import datetime, timezone
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.deliver import outbox
    from genios_engine.deliver import push
    from genios_engine.deliver.agent_api import poll_signals
    org, card_id = live["org"], live["card_id"]
    now = datetime.now(timezone.utc)
    with _engine().connect() as c:
        assert push._card_projection(c, org, card_id) is None
        pushable = [r[0] for r in c.execute(text("select k.card_id " + outbox.PUSHABLE_CARDS_SQL),
                                            {"o": org, "authority_time": now})]
        assert card_id not in pushable
    polled = poll_signals(GraphStore(URL), org, "agent_s36u2", eval_time=now)
    assert card_id not in [r["card_id"] for r in polled]


def test_a_meeting_followup_reaches_every_reader_a_person_reads(client, monkeypatch):
    live = _followup(client)
    _cards_queue_has_it(live)
    _person_readers_show_it(live, monkeypatch)


def test_a_question_card_reaches_every_reader_a_person_reads(world, cards, monkeypatch):
    live = _question(world, cards)
    _cards_queue_has_it(live)
    _person_readers_show_it(live, monkeypatch)


def test_neither_reaches_a_push_lane_or_the_agent_poll(client, world, cards):
    from genios_engine.deliver.store import PUSH_CARD_DOORS
    assert PUSH_CARD_DOORS == ("decision",)
    for live in (_followup(client), _question(world, cards)):
        _cards_queue_has_it(live)
        _push_readers_do_not(live)


def test_a_card_past_its_expiry_leaves_every_person_reader(client, monkeypatch):
    """The fragment carries liveness, not only the door: an expired follow-up is on no reader."""
    from genios_engine.api import workspace_routes as WR
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.mcp import server as MCP
    live = _followup(client)
    with _engine().begin() as c:
        c.execute(text("update cards set expires_at = now() - interval '1 minute' where card_id = :k"),
                  {"k": live["card_id"]})
    graph = GraphStore(URL)
    monkeypatch.setattr(WR, "_store", lambda: graph)
    assert live["card_id"] not in [p["card_id"] for p in WR.build_morning_brief(live["org"])["priorities"]]
    assert live["card_id"] not in [r["card_id"] for r in MCP._session_cards(graph.engine, live["org"])]

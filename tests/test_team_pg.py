"""P4 group A against real Postgres — the Voltex scenarios (SCREEN_INTEL_P4_BUILD.md §7 items 1–2):

  1. Anisha away (today+2 … today+9) with a commitment owed to Emru due today+5 → Emru gets ONE card
     + ONE `team` moment (with the realtime event); a rerun emits nothing; Shalini (`covers` Anisha)
     is proposed with evidence; once Shalini is also away the SAME card says there is no cover.
  2. A private screen fact about Anisha / the commitment never reaches a team card or moment.
  3. Milestone "ISO audit" (owner Emru, task_filter ISO) with three seats away before it →
     readiness counts from a FAKE Linear board through the real connector → mapping → graph path;
     the pass sends Emru the readiness card.
  4. /v1/team/away: seats only, who + when, no reason (sick → leave), private windows excluded.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_p4_a \\
        pytest tests/test_team_pg.py -q
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.platform.config import get_settings

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

NOW = datetime.now(timezone.utc).replace(microsecond=0)
TODAY = NOW.date()
SECRET = "SECRET-PRIVATE-SCREEN-FACT"
_ORGS: list[str] = []


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import (account_routes, auth_routes, capture_routes, device_routes,
                                   moment_routes, team_routes)
    app = FastAPI()
    for module in (auth_routes, account_routes, device_routes, capture_routes, moment_routes,
                   team_routes):
        app.include_router(module.router)
    settings = get_settings()
    old = settings.dashboard_url
    settings.dashboard_url = "https://app.genios.test"
    yield TestClient(app)
    settings.dashboard_url = old
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _voltex(client) -> dict:
    """Emru = the owner seat; Anisha, Shalini, Ravi = member seats. Person nodes for all four."""
    uid = uuid.uuid4().hex[:8]
    emru = f"emru_{uid}@voltex.test"
    res = client.post("/auth/register", json={"name": "Emru", "password": "founder-pass-1",
                                              "email": emru, "company": f"Voltex {uid}"})
    assert res.status_code == 200, res.text
    body = res.json()
    org = body["org_id"]
    _ORGS.append(org)
    for payload in ({"enabled": True}, {"moments_display": True}):
        r = client.put("/v1/capture/policy", json=payload, headers=H(body["token"]))
        assert r.status_code == 200, r.text
    seats = {"emru": body["seat_id"], "anisha": f"seat_ani_{uid}", "shalini": f"seat_sha_{uid}",
             "ravi": f"seat_rav_{uid}"}
    mails = {"emru": emru, "anisha": f"anisha_{uid}@voltex.test",
             "shalini": f"shalini_{uid}@voltex.test", "ravi": f"ravi_{uid}@voltex.test"}
    names = {"emru": "Emru", "anisha": "Anisha Rao", "shalini": "Shalini Iyer", "ravi": "Ravi Kumar"}
    nodes = {k: f"node_{k}_{uid}" for k in names}
    with _engine().begin() as c:
        for k in ("anisha", "shalini", "ravi"):
            c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) "
                           "values (:o, :s, :e, 'member', true)"),
                      {"o": org, "s": seats[k], "e": mails[k]})
        for k in names:
            c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                           "canonical_key, display_name) values (:n, 1, :o, 'person', :k, :d)"),
                      {"n": nodes[k], "o": org, "k": mails[k], "d": names[k]})
    return {"org": org, "token": body["token"], "seats": seats, "mails": mails, "nodes": nodes,
            "uid": uid}


def _fact(c, org, subj, field, value, *, scope="org", who=None, event=None):
    fid = uuid.uuid4().hex[:12]
    c.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, "
        "visibility_scope, visibility_principals, created_by_event_id) values (:v, :f, :o, :s, "
        ":field, cast(:val as jsonb), :scope, cast(:who as text[]), :ev)"),
        {"v": "fv_" + fid, "f": "f_" + fid, "o": org, "s": subj, "field": field,
         "val": json.dumps(value), "scope": scope, "who": who, "ev": event})


def _away(ws, who, start_days, end_days, *, kind="leave", scope="org"):
    with _engine().begin() as c:
        _fact(c, ws["org"], ws["nodes"][who], "person.availability",
              {"kind": kind, "from": (TODAY + timedelta(days=start_days)).isoformat(),
               "to": (TODAY + timedelta(days=end_days)).isoformat(), "cover": None},
              scope=scope, who=[ws["mails"][who]] if scope == "private" else None)


def _commitment(ws, *, due_days=5) -> str:
    """Anisha owes Emru the ISO evidence pack; plus Anisha's private screen overlays."""
    org, cm = ws["org"], f"node_cmt_{ws['uid']}"
    with _engine().begin() as c:
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n, 1, :o, 'commitment', :k, :d)"),
                  {"n": cm, "o": org, "k": f"commitment:{cm}", "d": "send the ISO evidence pack"})
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                       "from_node_id, to_node_id) values (:v, :e, :o, 'owns', :f, :t)"),
                  {"v": "ev_" + cm, "e": "e_" + cm, "o": org, "f": ws["nodes"]["anisha"],
                   "t": cm})
        for field, value in (("commitment.text", "send the ISO evidence pack"),
                             ("commitment.status", "open"),
                             ("commitment.owner", ws["mails"]["anisha"]),
                             ("commitment.owed_to", "Emru"),
                             ("commitment.due_at", (NOW + timedelta(days=due_days)).isoformat())):
            _fact(c, org, cm, field, value)
        # PRIVATE overlays learned from Anisha's own screen — must never reach Emru.
        _fact(c, org, cm, "commitment.text", f"{SECRET} pack", scope="private",
              who=[ws["mails"]["anisha"]])
        _fact(c, org, ws["nodes"]["anisha"], "relationship.stance", SECRET, scope="private",
              who=[ws["mails"]["anisha"]])
    return cm


def _covers(ws, who, whom):
    with _engine().begin() as c:
        c.execute(text(
            "insert into seat_responsibilities (org_id, seat_id, scope_kind, scope_key, "
            "accountability, source, valid_from) values (:o, :s, 'person', :k, 'covers', "
            "'admin_declared', :f)"),
            {"o": ws["org"], "s": ws["seats"][who], "k": ws["mails"][whom],
             "f": NOW - timedelta(days=30)})


def _post_pass(ws) -> dict:
    from genios_engine.reason.team.postpass import run_post_passes
    return run_post_passes(_engine(), None, ws["org"], now=NOW)


def _team_pass(ws) -> int:
    """The team pass's count. Other registered passes (group B's verify) may report too — every
    value must be an int, and only `team` is this suite's business."""
    out = _post_pass(ws)
    assert all(isinstance(v, int) for v in out.values()), out
    return out["team"]


def _rows(sql: str, **params) -> list:
    with _engine().connect() as c:
        return c.execute(text(sql), params).mappings().all()


def _team_cards(ws, capability):
    return _rows("select * from cards where org_id=:o and capability_key=:c", o=ws["org"],
                 c=capability)


# ── 1 + 2 · away / deadline at risk / cover / privacy ─────────────────────────────────────────
def test_away_owner_deadline_one_card_one_moment_cover_and_rerun(client):
    ws = _voltex(client)
    _away(ws, "anisha", 2, 9)
    cm = _commitment(ws, due_days=5)
    _covers(ws, "shalini", "anisha")
    emru = ws["seats"]["emru"]

    assert _team_pass(ws) == 1
    cards = _team_cards(ws, "team.deadline_at_risk")
    assert len(cards) == 1
    card = cards[0]
    assert card["assignee"] == emru and card["domain"] == "team" and card["state"] == "queued"
    assert card["urgency_band"] == "high" and "Anisha Rao" in card["headline"]
    assert "Shalini Iyer" in card["situation"], card["situation"]
    assert any(e.get("kind") == "responsibility" and e.get("accountability") == "covers"
               for e in card["why"])
    moments = _rows("select * from moments where org_id=:o and seat_id=:s and kind='team'",
                    o=ws["org"], s=emru)
    assert len(moments) == 1
    m = moments[0]
    assert m["card_id"] == card["card_id"] and m["priority"] == "high" and m["display"] is True
    assert m["actions"][-1] == {"id": "open_card", "payload": {
        "card_id": card["card_id"],
        "url": f"https://app.genios.test/dashboard/cards?card={card['card_id']}"}}
    assert any(a["id"] == "assign_cover" and a["payload"]["seat_id"] == ws["seats"]["shalini"]
               for a in m["actions"])
    events = _rows("select * from realtime_events where org_id=:o and seat_id=:s "
                   "and kind='moment.new'", o=ws["org"], s=emru)
    assert len(events) == 1 and events[0]["payload"]["moment_id"] == m["moment_id"]
    sit = _rows("select * from team_situations where org_id=:o", o=ws["org"])
    assert len(sit) == 1 and sit[0]["card_id"] == card["card_id"] and cm in sit[0]["subject_node_ids"]
    # nobody else hears about it, and the absent owner is not told about her own absence
    assert _rows("select 1 from moments where org_id=:o and seat_id<>:s", o=ws["org"], s=emru) == []

    # PRIVACY: Anisha's private overlays never reach Emru's card, moment or realtime payload.
    blob = json.dumps([dict(card), dict(m), dict(events[0])], default=str)
    assert SECRET not in blob

    # RERUN: nothing new.
    assert _team_pass(ws) == 0
    assert len(_team_cards(ws, "team.deadline_at_risk")) == 1
    assert len(_rows("select 1 from moments where org_id=:o", o=ws["org"])) == 1

    # Shalini goes away too → the SAME card now says there is no cover; one new moment.
    _away(ws, "shalini", 3, 6)
    assert _team_pass(ws) == 1
    cards = _team_cards(ws, "team.deadline_at_risk")
    assert len(cards) == 1 and cards[0]["card_id"] == card["card_id"]
    assert "No cover available: Shalini Iyer is also away." in cards[0]["situation"] or \
        "No cover" in cards[0]["situation"], cards[0]["situation"]
    ms = _rows("select * from moments where org_id=:o", o=ws["org"])   # same NOW: no order
    latest = [m for m in ms if "No cover available: Shalini Iyer is also away." in m["body"]]
    assert len(ms) == 2 and len(latest) == 1, [m["body"] for m in ms]
    assert not any(a["id"] == "assign_cover" for a in latest[0]["actions"])
    assert SECRET not in json.dumps([dict(r) for r in ms], default=str)


# ── 3 · readiness from a fake Linear board ────────────────────────────────────────────────────
class FakeComposio:
    def __init__(self, issues):
        self.issues = issues

    def execute(self, slug, args):
        return {"issues": {"nodes": self.issues,
                           "pageInfo": {"hasNextPage": False, "endCursor": None}}}


def _issue(i, title, state_type, labels=("iso",)):
    return {"id": f"lin_{i}", "identifier": f"OPS-{i}", "title": title,
            "state": {"name": state_type.title(), "type": state_type},
            "labels": {"nodes": [{"name": x} for x in labels]},
            "project": {"name": "Compliance"}, "updatedAt": NOW.isoformat()}


def _ingest_linear(ws, issues) -> int:
    """Fake board → the real connector → linear.issue.v1 → commit_structured (the L2 lane)."""
    from genios_engine.capture.connectors.linear import ComposioLinearConnector
    from genios_engine.capture.structured.apply import apply_mapping
    from genios_engine.capture.structured.registry import all_mappings
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.structured import commit_structured
    mapping = next(m for m in all_mappings() if m.mapping_id == "linear.issue.v1")
    batch = ComposioLinearConnector(api_key="", user_id="",
                                    executor=FakeComposio(issues)).initial_snapshot()
    store = GraphStore(URL)
    for obj in batch.objects:
        ev = f"evt_{ws['uid']}_{obj.source_object_id}"
        with _engine().begin() as c:
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at) values (:e, :o, 'conn_linear', "
                "'linear', 'issue', :sid, :e, '{}'::jsonb, :at)"),
                {"e": ev, "o": ws["org"], "sid": obj.source_object_id, "at": obj.occurred_at})
        commit_structured(store, org_id=ws["org"], event_id=ev, source="linear",
                          source_object_id=obj.source_object_id,
                          structured_fields=apply_mapping(mapping, obj.raw), node_type="task",
                          occurred_at=obj.occurred_at, display_name=obj.raw.get("title"))
    return len(batch.objects)


def test_readiness_counts_from_fake_linear_board_and_three_seats_away(client):
    ws = _voltex(client)
    board = [_issue(1, "Collect access logs", "completed"),
             _issue(2, "Sign risk register", "completed"),
             _issue(3, "Policy review", "started"),
             _issue(4, "Old duplicate", "canceled"),
             _issue(5, "Website copy", "unstarted", labels=("marketing",))]
    assert _ingest_linear(ws, board) == 5
    for who, (a, b) in {"anisha": (2, 9), "shalini": (3, 4), "ravi": (1, 2)}.items():
        _away(ws, who, a, b)
    _commitment(ws, due_days=5)         # owed to Emru, open → one pending commitment

    bad = client.post("/v1/team/milestones", headers=H(ws["token"]), json={
        "title": "ISO audit", "due_at": (NOW + timedelta(days=6)).isoformat(),
        "owner_seat_id": ws["seats"]["emru"], "task_filter": {"label": "iso"}})
    assert bad.status_code == 422, bad.text
    res = client.post("/v1/team/milestones", headers=H(ws["token"]), json={
        "title": "ISO audit", "due_at": (NOW + timedelta(days=6)).isoformat(),
        "owner_seat_id": ws["seats"]["emru"], "scope_kind": None, "scope_key": None,
        "task_filter": {"query": "iso"}})
    assert res.status_code == 200, res.text
    item = res.json()
    assert set(item) == {"milestone_id", "title", "due_at", "owner_seat_id", "owner_name",
                         "scope_kind", "scope_key", "done", "pending", "away", "away_names"}
    # tasks: 2 completed ISO, 1 started ISO, canceled + non-ISO ignored; + Anisha's open commitment
    assert (item["done"], item["pending"], item["away"]) == (2, 2, 3), item
    assert item["away_names"] == ["Anisha Rao", "Ravi Kumar", "Shalini Iyer"]
    assert item["owner_name"] == "Emru" and item["scope_kind"] is None
    listed = client.get("/v1/team/milestones", headers=H(ws["token"]))
    assert listed.status_code == 200 and listed.json() == [item]

    assert _team_pass(ws) == 2                          # the deadline card + the readiness card
    ready = _team_cards(ws, "team.readiness")
    assert len(ready) == 1 and ready[0]["assignee"] == ws["seats"]["emru"]
    assert "3 away" in ready[0]["headline"] and "2 pending" in ready[0]["headline"]
    assert _team_pass(ws) == 0


# ── 5 · the situation card is in its recipient's normal queue, and only theirs ────────────────
def test_team_card_in_recipients_queue_only_and_authority_not_weakened(client):
    from genios_engine.deliver.store import CardStore
    ws = _voltex(client)
    _away(ws, "anisha", 2, 9)
    _commitment(ws, due_days=5)
    assert _team_pass(ws) == 1
    card = _team_cards(ws, "team.deadline_at_risk")[0]
    emru, anisha = ws["seats"]["emru"], ws["seats"]["anisha"]
    # A look-alike NOT written by emit_situation (no L4 run, other builder) must stay hidden.
    with _engine().begin() as c:
        c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
                       "reason_code, eval_time, capability_id) values (:s, :o, 'team.fake', 'n', "
                       "99, 'team', now(), 'team.fake')"), {"s": f"sig_fake_{ws['uid']}",
                                                             "o": ws["org"]})
        c.execute(text("insert into cards (card_id, signal_id, org_id, assignee, level, "
                       "urgency_band, headline, situation, score, state, expires_at, "
                       "builder_version) values (:k, :s, :o, :a, 'observation', 'high', 'fake', "
                       "'fake', 99, 'queued', now() + interval '1 day', 'other.v1')"),
                  {"k": f"card_fake_{ws['uid']}", "s": f"sig_fake_{ws['uid']}", "o": ws["org"],
                   "a": emru})
    store = CardStore(URL)
    for strict in (True, False):
        mine = store.queue(ws["org"], assignee=emru, strict_seat=strict, record_impressions=False)
        assert [r["card_id"] for r in mine] == [card["card_id"]], (strict, mine)
        theirs = store.queue(ws["org"], assignee=anisha, strict_seat=strict,
                             record_impressions=False)
        assert card["card_id"] not in [r["card_id"] for r in theirs]
    # `GET /cards` (api/routes.list_cards) is a thin wrapper over exactly these queue() calls.


# ── 6 · the local-gate flow: a teammate's screen mail "I will send YOU …" ─────────────────────
def test_screen_mail_promise_to_the_reader_reaches_him_with_project_cover(client):
    """Reproduces the local prod-copy gate: Emru's device read Anisha's mail "I will send you the
    ISO audit documents by 18 Sep". L2 wrote the commitment with an `owns` edge from Anisha and NO
    owed_to / owner fact; Emru has no person node; Anisha owns and Shalini covers
    ('project', 'iso audit')."""
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.deliver.actions import ingest_action
    from genios_engine.deliver.store import CardStore
    ws = _voltex(client)
    org, emru = ws["org"], ws["seats"]["emru"]
    ev, cm = f"evt_scr_{ws['uid']}", f"node_cmt_{ws['uid']}"
    with _engine().begin() as c:
        c.execute(text("delete from graph_nodes where org_id=:o and node_id=:n"),
                  {"o": org, "n": ws["nodes"]["emru"]})
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, recipients, visibility_scope, "
            "visibility_principals) values (:e, :o, :conn, 'screen_session', "
            "'screen_email_thread', :e, :e, cast(:actor as jsonb), :at, cast(:r as text[]), "
            "'private', cast(:r as text[]))"),
            {"e": ev, "o": org, "conn": f"screen:{emru}", "at": NOW,
             "actor": json.dumps({"name": "Anisha", "email": ws["mails"]["anisha"]}),
             "r": [ws["mails"]["emru"]]})
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n, 1, :o, 'commitment', :k, :d)"),
                  {"n": cm, "o": org, "k": f"commitment:{cm}", "d": "send ISO audit documents"})
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                       "from_node_id, to_node_id) values (:v, :e, :o, 'owns', :f, :t)"),
                  {"v": "ev_" + cm, "e": "e_" + cm, "o": org, "f": ws["nodes"]["anisha"],
                   "t": cm})
        for field, value in (("commitment.text", "send ISO audit documents"),
                             ("commitment.status", "open"),
                             ("commitment.due_at", (NOW + timedelta(days=5)).isoformat())):
            _fact(c, org, cm, field, value, event=ev)
        for seat, acc in (("anisha", "owns"), ("shalini", "covers")):
            c.execute(text(
                "insert into seat_responsibilities (org_id, seat_id, scope_kind, scope_key, "
                "accountability, source, valid_from) values (:o, :s, 'project', 'iso audit', "
                ":a, 'admin_declared', :f)"),
                {"o": org, "s": ws["seats"][seat], "a": acc, "f": NOW - timedelta(days=30)})
    _away(ws, "anisha", 2, 9)

    assert _team_pass(ws) == 1
    cards = _team_cards(ws, "team.deadline_at_risk")
    assert len(cards) == 1 and cards[0]["assignee"] == emru, cards
    card = cards[0]
    assert "owes you" in card["situation"] and "Shalini Iyer" in card["situation"], card

    # detail + act work on the situation card (same recipient rules as every card)
    store = CardStore(URL)
    assert store.get_authoritative_card(card["card_id"], org)["card_id"] == card["card_id"]
    wrong = ingest_action(card_store=None, graph=GraphStore(URL), org_id=org,
                          card_id=card["card_id"], actor=ws["seats"]["anisha"], action="snooze",
                          snooze_option="4h")
    assert wrong == {"ok": False, "error": "assigned_to_different_seat"}
    out = ingest_action(card_store=None, graph=GraphStore(URL), org_id=org,
                        card_id=card["card_id"], actor=emru, action="snooze", snooze_option="4h")
    assert out.get("ok") is not False, out
    assert _rows("select state from cards where card_id=:c", c=card["card_id"])[0]["state"] \
        == "snoozed"

    # Shalini away too → no cover; readiness scoped to the project still counts EVERY seat away
    _away(ws, "shalini", 3, 8)
    _away(ws, "ravi", 3, 8)
    assert _team_pass(ws) == 1
    bodies = [r["body"] for r in _rows("select body from moments where org_id=:o", o=org)]
    assert any("No cover available: Shalini Iyer is also away." in b for b in bodies), bodies
    # the snoozed card was answered, so a NEW card carries the change and the snoozed one is
    # resolved as superseded — never two live cards for one situation
    states = sorted(r["state"] for r in _team_cards(ws, "team.deadline_at_risk"))
    assert states == ["queued", "resolved"], states
    res = client.post("/v1/team/milestones", headers=H(ws["token"]), json={
        "title": "ISO audit", "due_at": (NOW + timedelta(days=6)).isoformat(),
        "owner_seat_id": emru, "scope_kind": "project", "scope_key": "iso audit",
        "task_filter": None})
    assert res.status_code == 200, res.text
    assert res.json()["away"] == 3 and res.json()["pending"] == 1, res.json()


# ── 7 · the cover survives the card's 140-char clip; one chain run rewrites it ────────────────
def test_first_card_names_available_cover_and_next_pass_rewrites_it(client):
    ws = _voltex(client)
    org, cm = ws["org"], f"node_cmt_{ws['uid']}"
    long_text = ("send the complete ISO audit evidence documents, signed access logs and the "
                 "updated risk register")
    with _engine().begin() as c:
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n, 1, :o, 'commitment', :k, :d)"),
                  {"n": cm, "o": org, "k": f"commitment:{cm}", "d": long_text[:80]})
        for field, value in (("commitment.text", long_text), ("commitment.status", "open"),
                             ("commitment.owner", ws["mails"]["anisha"]),
                             ("commitment.owed_to", "Emru"),
                             ("commitment.due_at", (NOW + timedelta(days=5)).isoformat())):
            _fact(c, org, cm, field, value)
        for seat, acc in (("anisha", "owns"), ("shalini", "covers")):
            c.execute(text(
                "insert into seat_responsibilities (org_id, seat_id, scope_kind, scope_key, "
                "accountability, source, valid_from) values (:o, :s, 'project', 'iso audit', "
                ":a, 'admin_declared', :f)"),
                {"o": org, "s": ws["seats"][seat], "a": acc, "f": NOW - timedelta(days=30)})
    _away(ws, "anisha", 2, 9)

    assert _team_pass(ws) == 1
    card = _team_cards(ws, "team.deadline_at_risk")[0]
    assert card["situation"].startswith("Proposed cover: Shalini Iyer (covers project iso audit)."), \
        card["situation"]
    assert any(e.get("kind") == "responsibility" and e.get("seat_id") == ws["seats"]["shalini"]
               for e in card["why"])

    _away(ws, "shalini", 3, 8)                          # her OOO lands → ONE pass rewrites it
    assert _team_pass(ws) == 1
    after = _team_cards(ws, "team.deadline_at_risk")
    assert len(after) == 1 and after[0]["card_id"] == card["card_id"]
    assert after[0]["situation"].startswith("No cover available: Shalini Iyer is also away."), \
        after[0]["situation"]
    history = _rows("select kind, detail from card_events where card_id=:c order by occurred_at",
                    c=card["card_id"])
    assert [h["kind"] for h in history] == ["card.created", "card.rebuilt"]
    assert history[0]["detail"]["situation"].startswith("Proposed cover: Shalini Iyer")
    assert history[1]["detail"]["situation"].startswith("No cover available")


# ── 4 · the away view ─────────────────────────────────────────────────────────────────────────
def test_team_away_is_who_and_when_only(client):
    ws = _voltex(client)
    _away(ws, "anisha", 2, 9, kind="sick")
    _away(ws, "ravi", 1, 3, scope="private")           # private overlay → not a team fact
    with _engine().begin() as c:                        # an external person away: not a seat
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n, 1, :o, 'person', "
                       "'priya@acme.test', 'Priya Shah')"),
                  {"n": f"node_priya_{ws['uid']}", "o": ws["org"]})
        _fact(c, ws["org"], f"node_priya_{ws['uid']}", "person.availability",
              {"kind": "ooo", "from": TODAY.isoformat(), "to": TODAY.isoformat()})
    res = client.get("/v1/team/away", headers=H(ws["token"]),
                     params={"from": TODAY.isoformat(),
                             "to": (TODAY + timedelta(days=14)).isoformat()})
    assert res.status_code == 200, res.text
    assert res.json() == [{"seat_id": ws["seats"]["anisha"], "name": "Anisha Rao",
                           "start": (TODAY + timedelta(days=2)).isoformat(),
                           "end": (TODAY + timedelta(days=9)).isoformat(), "kind": "leave"}]
    assert client.get("/v1/team/away", headers=H(ws["token"]),
                      params={"from": "2026-09-20", "to": "2026-09-01"}).status_code == 422

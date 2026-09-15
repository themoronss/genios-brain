"""P5 group B against real Postgres (SCREEN_INTEL_P5_BUILD.md §3, §7):

  1. prep: the owner's device evaluates a meeting it attends in 15 min → ≥ 1 open loop per known
     attendee (theirs + ours), the last meeting's still-open item (`raised_in`), the deal change,
     pinned `open_meeting` action, TTL to start + 10 min, ≤ 1.2 s;
  2. a seat that does not attend (and an unknown meeting) → 204;
  3. the prep never shows another seat's private fact (overlay, private commitment text, private
     `raised_in` evidence) — the positive control shows it to its own seat; the pass precomputes
     preps for device seats and evaluate serves the re-timed cache;
  4. follow-up: one `meeting.followup` card + moment per principal seat, filtered per seat, none
     for a seat outside the transcript; a rerun emits nothing.

The `transcripts` table and `raised_in` edges are group A's: this file creates the minimal rows
itself (fixture DDL below, from the §3 contract).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_p5_b \\
        pytest tests/test_meetings_pg.py -q
"""
from __future__ import annotations

import json
import os
import time
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

SECRET = "SECRET-MEMBER-ONLY"
_ORGS: list[str] = []

# Group A's 0155 `transcripts` DDL, verbatim (p5/ingest) — until A merges, the scratch DB lacks it.
_TRANSCRIPTS_DDL = """
create table if not exists transcripts (
    transcript_id     text primary key,
    org_id            text not null references orgs (id) on delete cascade,
    source            text not null,
    source_ref        text not null,
    file_id           text,
    seat_id           text,
    uploader_email    text,
    provider          text not null default 'other'
                      check (provider in ('gmeet', 'granola', 'fireflies', 'otter', 'zoom',
                                          'teams', 'other')),
    scope             text not null default 'attendees'
                      check (scope in ('attendees', 'personal')),
    calendar_event_id text,
    meeting_node_id   text,
    title             text,
    started_at        timestamptz,
    ended_at          timestamptz,
    meeting           jsonb not null default '{}'::jsonb,
    speakers          jsonb not null default '[]'::jsonb,
    attendees         jsonb not null default '[]'::jsonb,
    principals        text[] not null default '{}',
    parts             integer not null default 0,
    event_ids         text[] not null default '{}',
    content_hash      text not null,
    content_version   text,
    enc_text          bytea,
    status            text not null default 'queued'
                      check (status in ('queued', 'extracting', 'extracted', 'failed')),
    error             text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),
    unique (org_id, source, source_ref)
)"""


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import (account_routes, auth_routes, capture_routes, device_routes,
                                   moment_routes)
    app = FastAPI()
    for module in (auth_routes, account_routes, device_routes, capture_routes, moment_routes):
        app.include_router(module.router)
    settings = get_settings()
    old = settings.dashboard_url
    settings.dashboard_url = "https://app.genios.test"
    yield TestClient(app)
    settings.dashboard_url = old
    from genios_engine.platform.realtime import stop_realtime
    stop_realtime()
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


def _ws(client) -> dict:
    from tests.test_moments_pg import _workspace
    ws = _workspace(client)
    _ORGS.append(ws["org"])
    return ws


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _node(c, org, nid, typ, key, name):
    c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
                   "display_name) values (:n, 1, :o, :t, :k, :d)"),
              {"n": nid, "o": org, "t": typ, "k": key, "d": name})


def _alias(c, org, typ, key, nid):
    c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id) "
                   "values (:o, :t, :k, :n)"), {"o": org, "t": typ, "k": key, "n": nid})


def _edge(c, org, typ, frm, to, event=None):
    eid = uuid.uuid4().hex[:12]
    c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                   "from_node_id, to_node_id, created_by_event_id) values "
                   "(:v, :e, :o, :t, :f, :to, :ev)"),
              {"v": "ev_" + eid, "e": "e_" + eid, "o": org, "t": typ, "f": frm, "to": to,
               "ev": event})


def _fact(c, org, subj, field, value, *, scope="org", who=None, status="active",
          valid_from=None, valid_to=None, event=None, quote=None):
    fid = uuid.uuid4().hex[:12]
    c.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, "
        "visibility_scope, visibility_principals, status, valid_from, valid_to, "
        "created_by_event_id) values (:v, :f, :o, :s, :field, cast(:val as jsonb), :scope, "
        "cast(:who as text[]), :st, coalesce(cast(:vf as timestamptz), now()), :vt, :ev)"),
        {"v": "fv_" + fid, "f": "f_" + fid, "o": org, "s": subj, "field": field,
         "val": json.dumps(value), "scope": scope, "who": who, "st": status, "vf": valid_from,
         "vt": valid_to, "ev": event})
    if quote is not None:          # the fact's evidence quote, as the pipeline's source ref
        c.execute(text("insert into graph_source_refs (source_ref_id, org_id, fact_version_id, "
                       "event_id, evidence) values (:r, :o, :v, :e, cast(:ev as jsonb))"),
                  {"r": "ref_" + fid, "o": org, "v": "fv_" + fid, "e": event or "evt_none",
                   "ev": json.dumps({"text": quote})})


def _event(c, org, *, days_ago=0.0, scope="org", who=None) -> str:
    ev = f"evt_{uuid.uuid4().hex[:10]}"
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, visibility_scope, visibility_principals) "
        "values (:e, :o, 'conn', 'gmail', 'message', :e, :e, '{}'::jsonb, :at, :scope, "
        "cast(:who as text[]))"),
        {"e": ev, "o": org, "at": datetime.now(timezone.utc) - timedelta(days=days_ago),
         "scope": scope, "who": who})
    return ev


def _commitment(c, org, nid, text_, *, owner=None, owed_to=None, due=None, status="open",
                scope="org", who=None, event=None):
    _node(c, org, nid, "commitment", f"commitment:{nid}", text_ if scope == "org" else "x")
    if owner:
        _edge(c, org, "owns", owner, nid, event)
    _fact(c, org, nid, "commitment.text", text_, scope=scope, who=who, event=event)
    _fact(c, org, nid, "commitment.status", status)
    if owed_to:
        _fact(c, org, nid, "commitment.owed_to", owed_to)
    if due:
        _fact(c, org, nid, "commitment.due_at", due.isoformat())


def _seed(ws: dict, *, start: datetime) -> dict:
    """Acme review (owner + Priya @ Acme + Ravi) in 15 min; the Acme kickoff 7 d ago (owner +
    Priya) raised an item still open; the member holds private knowledge about Priya."""
    org = ws["org"]
    o_mail, m_mail = ws["owner"]["email"].lower(), ws["member"]["email"].lower()
    n = {k: f"node_{k}_{uuid.uuid4().hex[:8]}" for k in
         ("me1", "me2", "priya", "ravi", "acme", "deal", "mtg", "prev", "mtg2", "c_theirs",
          "c_mine", "c_prev", "c_priv", "c_privedge")}
    now = datetime.now(timezone.utc)
    with _engine().begin() as c:
        for k, typ, key, name in (("me1", "person", o_mail, "Founder"),
                                  ("me2", "person", m_mail, "Member"),
                                  ("priya", "person", "priya@acme.test", "Priya Shah"),
                                  ("ravi", "person", "ravi@ravico.test", "Ravi Kumar"),
                                  ("acme", "company", "acme.test", "Acme Logistics"),
                                  ("deal", "deal", f"deal:{n['deal']}", "Acme expansion"),
                                  ("mtg", "meeting", f"gcal:{n['mtg']}", "Acme review"),
                                  ("prev", "meeting", f"gcal:{n['prev']}", "Acme kickoff"),
                                  ("mtg2", "meeting", f"gcal:{n['mtg2']}", "Member x Priya")):
            _node(c, org, n[k], typ, key, name)
        for typ, key, k in (("email", o_mail, "me1"), ("email", m_mail, "me2"),
                            ("email", "priya@acme.test", "priya"),
                            ("email", "ravi@ravico.test", "ravi")):
            _alias(c, org, typ, key, n[k])
        for frm, to in (("me1", "mtg"), ("priya", "mtg"), ("ravi", "mtg"), ("me1", "prev"),
                        ("priya", "prev"), ("me2", "mtg2"), ("priya", "mtg2")):
            _edge(c, org, "attended", n[frm], n[to])
        _edge(c, org, "works_at", n["priya"], n["acme"])
        _edge(c, org, "about", n["deal"], n["acme"])
        for mid, title, at in (("mtg", "Acme review", start), ("prev", "Acme kickoff",
                                                               now - timedelta(days=7)),
                               ("mtg2", "Member x Priya", start + timedelta(minutes=30))):
            _fact(c, org, n[mid], "meeting.title", title)
            _fact(c, org, n[mid], "meeting.start_at", at.isoformat())
            _fact(c, org, n[mid], "meeting.end_at", (at + timedelta(hours=1)).isoformat())
        _fact(c, org, n["deal"], "deal.stage", "proposal", status="superseded",
              valid_from=now - timedelta(days=10), valid_to=now - timedelta(days=1))
        _fact(c, org, n["deal"], "deal.stage", "negotiation", valid_from=now - timedelta(days=1))
        _commitment(c, org, n["c_theirs"], "send the signed SOW", owner=n["priya"],
                    due=now + timedelta(days=3))
        _commitment(c, org, n["c_mine"], "share the pricing deck", owner=n["me1"],
                    owed_to="Ravi Kumar")
        _commitment(c, org, n["c_prev"], "confirm the pilot scope")
        _edge(c, org, "raised_in", n["c_prev"], n["prev"])
        # ── the MEMBER's private knowledge: must never reach the owner's prep ──
        _fact(c, org, n["priya"], "person.title", SECRET + " title", scope="private",
              who=[m_mail])
        _commitment(c, org, n["c_priv"], SECRET + " commitment", owner=n["priya"],
                    scope="private", who=[m_mail])
        priv_ev = _event(c, org, days_ago=7, scope="private", who=[m_mail])
        _commitment(c, org, n["c_privedge"], SECRET + " raised", scope="org")
        _edge(c, org, "raised_in", n["c_privedge"], n["prev"], priv_ev)
        # Priya's last touch: an org-visible email 3 d ago
        ev = _event(c, org, days_ago=3)
        c.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "occurred_at, created_by_event_id) values (:i, :o, :s, 'event_presence', :at, :e)"),
            {"i": "obs_" + ev, "o": org, "s": n["priya"], "at": now - timedelta(days=3), "e": ev})
    return n


def _evaluate(client, dev: dict, meeting: str, rid: str | None = None):
    body = {"moment_request_id": rid or uuid.uuid4().hex,
            "surface": {"app": "zoom", "bundle_id": "us.zoom.xos"},
            "features": {"meeting_node_id": meeting}}
    return client.post("/v1/moments/evaluate", json=body, headers=H(dev["access_token"]))


# ── 1 · prep ──────────────────────────────────────────────────────────────────────────────────
def test_prep_lists_open_loops_per_known_attendee_fast(client):
    ws = _ws(client)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=15)
    n = _seed(ws, start=start)
    t0 = time.perf_counter()
    res = _evaluate(client, ws["owner_dev"], n["mtg"], rid="prep-1")
    elapsed = time.perf_counter() - t0
    assert res.status_code == 200, res.text
    assert elapsed < 1.2, elapsed
    m = res.json()
    assert m["capability_id"] == "moment.meeting_prep" and m["priority"] == "high"
    assert m["kind"] == "advice" and m["reason"] == "shadow"          # moments_display is off
    assert m["headline"].startswith("Acme review in 15 min") or \
        m["headline"].startswith("Acme review in 14 min")
    assert "open loops with Priya +1" in m["headline"]
    lines = m["body"].split("\n")
    assert len(lines) <= 4, lines
    priya = next(ln for ln in lines if ln.startswith("Priya Shah"))
    assert "Acme Logistics" in priya and "last touch 3 d ago" in priya
    assert "They owe: send the signed SOW" in priya and "Deal: negotiation" in priya
    ravi = next(ln for ln in lines if ln.startswith("Ravi Kumar"))
    assert "You owe: share the pricing deck" in ravi
    assert any(ln.startswith("Still open from Acme kickoff") and "confirm the pilot scope" in ln
               for ln in lines)
    assert "Changed: Acme Logistics deal stage proposal → negotiation" in lines
    assert m["actions"] == [{"id": "open_meeting",
                             "payload": {"meeting_node_id": n["mtg"], "url": None}}]
    assert abs(m["ttl_seconds"] - 25 * 60) <= 5
    assert SECRET not in res.text
    # a retry answers what the first did
    assert _evaluate(client, ws["owner_dev"], n["mtg"], rid="prep-1").json() == m



def test_prep_adds_the_seats_own_screen_item_on_an_attendee(client):
    # P11: an open screen follow-up the OWNER's screen caught on Ravi joins Ravi's line; the
    # member's own item on Ravi never reaches the owner's prep.
    ws = _ws(client)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=15)
    n = _seed(ws, start=start)
    with _engine().begin() as c:
        for fid, seat, note in (("fu_own_" + uuid.uuid4().hex[:8], ws["owner"]["seat_id"],
                                 "send the revised quote"),
                                ("fu_mem_" + uuid.uuid4().hex[:8], ws["member"]["seat_id"],
                                 "member private note")):
            c.execute(text(
                "insert into screen_followups (id, org_id, seat_id, kind, text, who, topic_key, "
                "subject_node_id) values (:i, :o, :s, 'ask', :t, 'Ravi Kumar', :k, :n)"),
                {"i": fid, "o": ws["org"], "s": seat, "t": note, "k": "k_" + fid,
                 "n": n["ravi"]})
    res = _evaluate(client, ws["owner_dev"], n["mtg"], rid="prep-screen")
    assert res.status_code == 200, res.text
    m = res.json()
    ravi = next(ln for ln in m["body"].split("\n") if ln.startswith("Ravi Kumar"))
    assert "They asked (on screen): send the revised quote" in ravi
    assert "member private note" not in res.text
    assert "4 open loops" in m["headline"]

# ── 2 · not an attendee ───────────────────────────────────────────────────────────────────────
def test_non_attendee_and_unknown_meeting_get_204(client):
    ws = _ws(client)
    n = _seed(ws, start=datetime.now(timezone.utc) + timedelta(minutes=15))
    assert _evaluate(client, ws["member_dev"], n["mtg"]).status_code == 204
    assert _evaluate(client, ws["owner_dev"], "node_nope").status_code == 204
    assert _evaluate(client, ws["owner_dev"], n["priya"]).status_code == 204   # not a meeting
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from moments where org_id = :o"),
                         {"o": ws["org"]}).scalar() == 0


# ── 3 · privacy + precompute ──────────────────────────────────────────────────────────────────
def test_prep_never_shows_another_seats_private_fact_and_serves_the_precompute(client):
    from genios_engine.reason.meetings import passes as MS
    ws = _ws(client)
    now = datetime.now(timezone.utc)
    n = _seed(ws, start=now + timedelta(minutes=15))
    # the pass precomputes for both device seats' meetings in the next 3 h
    assert MS.run(_engine(), None, ws["org"], now=now) == 0          # no transcripts → 0
    with _engine().connect() as c:
        rows = {r.seat_id: r.moment for r in c.execute(text(
            "select seat_id, moment from moment_cache where org_id = :o"), {"o": ws["org"]})}
    assert set(rows) == {ws["owner"]["seat_id"], ws["member"]["seat_id"]}
    owner_pre, member_pre = rows[ws["owner"]["seat_id"]], rows[ws["member"]["seat_id"]]
    assert SECRET not in json.dumps(owner_pre)
    assert owner_pre["prep"]["meeting_node_id"] == n["mtg"] and owner_pre["displayed"] is False
    # positive control: the member's OWN private knowledge reaches the member's prep
    assert f"{SECRET} title" in member_pre["body"] and f"{SECRET} commitment" in member_pre["body"]
    # a rerun writes nothing new
    MS.run(_engine(), None, ws["org"], now=now)
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from moment_cache where org_id = :o"),
                         {"o": ws["org"]}).scalar() == 2
    # evaluate serves the precompute, re-timed, never the member's secret
    res = _evaluate(client, ws["owner_dev"], n["mtg"])
    assert res.status_code == 200 and SECRET not in res.text
    assert res.json()["body"] == owner_pre["body"]
    assert "in 15 min" in res.json()["headline"] or "in 14 min" in res.json()["headline"]
    member = _evaluate(client, ws["member_dev"], n["mtg2"])
    assert member.status_code == 200 and f"{SECRET} title" in member.text


# ── 4 · follow-up ─────────────────────────────────────────────────────────────────────────────
def test_followup_once_per_attendee_seat_and_rerun_emits_nothing(client):
    from genios_engine.reason.meetings import passes as MS
    ws = _ws(client)
    org = ws["org"]
    o_mail, m_mail = ws["owner"]["email"].lower(), ws["member"]["email"].lower()
    outsider = f"seat_out_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    ended = now - timedelta(hours=2)
    n = {k: f"node_{k}_{uuid.uuid4().hex[:8]}" for k in
         ("me1", "me2", "priya", "mtg", "c_you", "c_priya", "c_priv", "c_loose")}
    tid = f"tr_{uuid.uuid4().hex[:10]}"
    with _engine().begin() as c:
        c.execute(text(_TRANSCRIPTS_DDL))
        c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) "
                       "values (:o, :s, :e, 'member', true)"),
                  {"o": org, "s": outsider, "e": f"{outsider}@acme-internal.test"})
        _node(c, org, n["me1"], "person", o_mail, "Emru Founder")
        _node(c, org, n["me2"], "person", m_mail, "Shalini Iyer")
        _node(c, org, n["priya"], "person", "priya@acme.test", "Priya Shah")
        _node(c, org, n["mtg"], "meeting", f"gcal:{n['mtg']}", "ISO audit prep")
        for key, k in ((o_mail, "me1"), (m_mail, "me2"), ("priya@acme.test", "priya")):
            _alias(c, org, "email", key, n[k])
        _fact(c, org, n["mtg"], "meeting.title", "ISO audit prep")
        _fact(c, org, n["mtg"], "meeting.start_at", ended.isoformat())
        # the transcript's own event: private to its principals (P5 §2.4)
        tev = _event(c, org, scope="private", who=[o_mail, m_mail])
        _commitment(c, org, n["c_you"], "send the ISO evidence pack", owner=n["me1"], event=tev,
                    due=now + timedelta(days=4))
        _commitment(c, org, n["c_priya"], "confirm the audit date", owner=n["priya"], event=tev)
        _commitment(c, org, n["c_priv"], SECRET + " scope", scope="private", who=[m_mail])
        # no raised_in edge: reached only through the transcript's part event (fact provenance)
        _commitment(c, org, n["c_loose"], "book the auditor", event=tev)
        for item in ("c_you", "c_priya"):
            _edge(c, org, "raised_in", n[item], n["mtg"], tev)
        priv = _event(c, org, scope="private", who=[m_mail])
        _edge(c, org, "raised_in", n["c_priv"], n["mtg"], priv)
        # decisions = `decision.status` facts on the MEETING node (A's pipeline): an earlier one
        # superseded by a later one from the same transcript — both are listed — plus one the
        # member alone may read, and one from ANOTHER source that is not this transcript's.
        _fact(c, org, n["mtg"], "decision.status", "made", scope="private",
              who=[o_mail, m_mail], event=tev, quote="We will go with Vendor X",
              status="superseded", valid_from=now - timedelta(hours=2),
              valid_to=now - timedelta(hours=1))
        _fact(c, org, n["mtg"], "decision.status", "made", scope="private",
              who=[o_mail, m_mail], event=tev, quote="Audit moves to 3 Oct",
              valid_from=now - timedelta(hours=1))
        _fact(c, org, n["mtg"], "decision.status", "pending", scope="private", who=[m_mail],
              event=tev, quote=SECRET + " pricing")
        other = _event(c, org)
        _fact(c, org, n["mtg"], "decision.status", "made", event=other, quote="unrelated call",
              status="superseded", valid_to=now - timedelta(minutes=30))
        c.execute(text(
            "insert into transcripts (transcript_id, org_id, source, source_ref, provider, status, "
            "scope, meeting_node_id, title, principals, meeting, event_ids, content_hash) values "
            "(:t, :o, 'upload', :t, 'granola', 'extracted', 'attendees', :mid, 'ISO audit prep', "
            "cast(:p as text[]), cast(:m as jsonb), cast(:ev as text[]), 'h1')"),
            {"t": tid, "o": org, "p": [o_mail, m_mail], "mid": n["mtg"], "ev": [tev],
             "m": json.dumps({"meeting_node_id": n["mtg"], "title": "ISO audit prep"})})
    assert MS.run(_engine(), None, org, now=now) == 2
    with _engine().connect() as c:
        sits = {r.seat_id: r for r in c.execute(text(
            "select t.seat_id, t.key, m.headline, m.body, m.capability_id, m.kind, m.actions "
            "from team_situations t join moments m on m.moment_id = t.moment_id "
            "where t.org_id = :o"), {"o": org})}
        cards = c.execute(text("select count(*) from cards where org_id = :o "
                               "and capability_key = 'meeting.followup'"), {"o": org}).scalar()
    assert set(sits) == {ws["owner"]["seat_id"], ws["member"]["seat_id"]} and cards == 2
    mine = sits[ws["owner"]["seat_id"]]
    assert mine.key == f"followup:{tid}:{ws['owner']['seat_id']}"
    assert mine.capability_id == "meeting.followup" and mine.kind == "team"
    assert mine.body.startswith("You: send the ISO evidence pack (due ")
    assert "Priya: confirm the audit date" in mine.body
    assert "No owner: book the auditor" in mine.body
    assert mine.body.endswith("Decided: We will go with Vendor X; Audit moves to 3 Oct")
    assert SECRET not in mine.body and SECRET not in mine.headline
    assert "unrelated call" not in mine.body
    assert mine.headline == "Follow-ups from ISO audit prep — 1 for you"
    assert {"id": "open_meeting", "payload": {"meeting_node_id": n["mtg"], "url": None}} \
        in mine.actions
    theirs = sits[ws["member"]["seat_id"]]
    assert "Emru: send the ISO evidence pack" in theirs.body and f"{SECRET} scope" in theirs.body
    assert theirs.body.endswith(f"Open decision: {SECRET} pricing")
    # rerun: nothing new, the outsider never got anything
    assert MS.run(_engine(), None, org, now=now + timedelta(minutes=5)) == 0
    with _engine().connect() as c:
        assert c.execute(text("select count(*) from moments where org_id = :o "
                              "and capability_id = 'meeting.followup'"), {"o": org}).scalar() == 2
        assert c.execute(text("select count(*) from team_situations where org_id = :o "
                              "and seat_id = :s"), {"o": org, "s": outsider}).scalar() == 0

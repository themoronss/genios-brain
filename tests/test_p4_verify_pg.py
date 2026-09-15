"""P4 group B against real Postgres — the scenarios SCREEN_INTEL_P4_BUILD.md §7 (3–5) names:

  1. counterparty decline → deal lost; the same words from the seat → nothing;
  2. higher-rank held status → discrepancy → verify situation to the owner; keep blocks the same
     challenger; the pass re-emits nothing;
  3. seat 2 never sees seat 1's private discrepancy (both endpoints); the principal accepts it;
  4. P-13 fires for org-visible touches only; `other_seats` never shows a screen-only touch;
  5. draft review: ≤ 2 notes, no rewrite field, the draft never stored.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_p4_b \\
        pytest tests/test_p4_verify_pg.py -q
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

from genios_engine.platform.auth import AuthCtx
from genios_engine.platform.config import get_settings
from tests.test_l2_db_e2e import _FakeLLM
from tests.test_moments_pg import _ORGS, H, _engine, _evaluate, _join, _register, _workspace

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

NOW = datetime.now(timezone.utc).replace(microsecond=0)
T0 = NOW - timedelta(days=3)
QUOTE = "we have decided to go with another vendor for this rollout"
BODY = (f"Hi Rohit, thank you for the proposal. After discussing internally {QUOTE}, so we won't "
        "be proceeding at this stage.")


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import (account_routes, auth_routes, capture_routes,
                                   device_routes, discrepancy_routes, moment_routes)
    app = FastAPI()
    for module in (auth_routes, account_routes, device_routes, capture_routes, moment_routes,
                   discrepancy_routes):
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


@pytest.fixture(scope="module")
def store():
    from genios_engine.context.graph_store import GraphStore
    return GraphStore(engine=_engine())


def _team(client) -> dict:
    owner = _register(client)
    member = _join(client, owner)
    return {"org": owner["org_id"], "owner": owner, "member": member,
            "internal": frozenset({owner["email"].lower(), member["email"].lower()})}


def _event(org: str, eid: str, *, source="gmail", object_type="email_message",
           actor: str | None = None, scope: str | None = None, principals=None,
           at: datetime | None = None) -> None:
    with _engine().begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, visibility_scope, "
            "visibility_principals) values (:e, :o, :conn, :src, :ot, :e, :e, cast(:a as jsonb), "
            ":at, :sc, :pr)"),
            {"e": eid, "o": org, "conn": f"conn_{source}", "src": source, "ot": object_type,
             "a": json.dumps({"type": "external_contact", "email": actor}), "at": at or NOW,
             "sc": scope, "pr": principals})


def _seed_deal(store, org: str, *, rank: int) -> tuple[str, str]:
    with store.engine.begin() as c:
        comp = store.find_or_create_node(c, org_id=org, node_type="company",
                                         canonical_key="acme.io", display_name="Acme Logistics",
                                         event_id="seed")
        deal = store.find_or_create_node(c, org_id=org, node_type="deal",
                                         canonical_key="deal:" + comp,
                                         display_name="Acme — deal", event_id="seed")
        store.write_edge(c, org_id=org, edge_type="owns", from_node_id=comp, to_node_id=deal,
                         confidence=0.9, occurred_at=T0, event_id="seed", evidence={},
                         source="hubspot", authority_rank=rank)
        store.write_fact(c, org_id=org, subject_node_id=deal, field="deal.status", value="open",
                         value_type="string", confidence=0.9, occurred_at=T0,
                         event_id=f"seed_{uuid.uuid4().hex[:8]}", evidence={},
                         source="hubspot" if rank >= 3 else "gmail", authority_rank=rank)
    return comp, deal


def _decline(store, team, eid, *, sender, recipients=(), inbound=True, at=None):
    from genios_engine.context.pipeline import process_event
    canned = {"relevance": 0.8, "noise_type": "none", "domains": [], "entity_mentions": [],
              "roles": [], "commitments": [], "scheduling_proposals": [], "questions": [],
              "observations": [],
              "fact_candidates": [{"subject": "Acme rollout vendor choice",
                                   "field": "decision.status", "value": "made",
                                   "evidence_text": QUOTE}]}
    return process_event(org_id=team["org"], event_id=eid, source="gmail",
                         content=BODY + f" [{eid}]", sender_email=sender,
                         recipient_emails=list(recipients), occurred_at=at or NOW,
                         llm=_FakeLLM(canned), store=store, is_inbound=inbound,
                         internal_emails=team["internal"])


def _status(org: str, deal: str) -> str:
    with _engine().connect() as c:
        return c.execute(text(
            "select value #>> '{}' from graph_facts where org_id=:o and subject_node_id=:d "
            "and field='deal.status' and valid_to is null and status='active' "
            "and visibility_scope is distinct from 'private'"), {"o": org, "d": deal}).scalar()


def _discrepancies(org: str) -> list:
    with _engine().connect() as c:
        return c.execute(text("select id, status, resolution, held, challenger from "
                              "discrepancies where org_id=:o order by created_at"),
                         {"o": org}).fetchall()


# ── 1 ───────────────────────────────────────────────────────────────────────────────────────────
def test_counterparty_decline_marks_the_deal_lost_and_the_seats_own_words_do_not(client, store):
    team = _team(client)
    org, seat_mail = team["org"], team["owner"]["email"].lower()
    _comp, deal = _seed_deal(store, org, rank=2)

    # the seat writing the same words to the buyer
    e1 = f"evt_out_{uuid.uuid4().hex[:8]}"
    _decline(store, team, e1, sender=seat_mail, recipients=["priya@acme.io"], inbound=False)
    # the seat's own outgoing screen line, even if mis-directed as inbound
    e2 = f"evt_sent_{uuid.uuid4().hex[:8]}"
    _event(org, e2, source="screen_session", object_type="screen_chat_sent", actor=seat_mail)
    _decline(store, team, e2, sender="priya@acme.io", recipients=[seat_mail])
    assert _status(org, deal) == "open"

    e3 = f"evt_in_{uuid.uuid4().hex[:8]}"
    _decline(store, team, e3, sender="priya@acme.io", recipients=[seat_mail])
    assert _status(org, deal) == "lost"
    with _engine().connect() as c:
        ev = c.execute(text(
            "select r.evidence from graph_facts f join graph_source_refs r "
            "on r.fact_version_id = f.fact_version_id where f.org_id=:o and f.subject_node_id=:d "
            "and f.field='deal.status' and f.valid_to is null"), {"o": org, "d": deal}).scalar()
    assert ev["derived"] == "counterparty decline (decision.*)" and QUOTE in ev["text"]
    assert _discrepancies(org) == []


def _words_only(store, team, eid, *, sender, recipients=(), inbound=True):
    """No decision.* fact at all — only the author's words and L1's negative reading (the eval's
    5/10 runs)."""
    from genios_engine.context.pipeline import process_event
    canned = {"relevance": 0.8, "noise_type": "none", "domains": [], "entity_mentions": [],
              "roles": [], "commitments": [], "scheduling_proposals": [], "questions": [],
              "observations": [], "fact_candidates": [], "intent": "inform", "stance": "negative"}
    return process_event(org_id=team["org"], event_id=eid, source="gmail",
                         content=BODY + f" [{eid}]", sender_email=sender,
                         recipient_emails=list(recipients), occurred_at=NOW,
                         llm=_FakeLLM(canned), store=store, is_inbound=inbound,
                         internal_emails=team["internal"])


def test_counterparty_words_decline_without_a_decision_fact(client, store):
    team = _team(client)
    org, seat_mail = team["org"], team["owner"]["email"].lower()
    _comp, deal = _seed_deal(store, org, rank=2)
    _words_only(store, team, f"evt_out_{uuid.uuid4().hex[:8]}", sender=seat_mail,
                recipients=["priya@acme.io"], inbound=False)          # the seat's own line
    assert _status(org, deal) == "open"
    _words_only(store, team, f"evt_in_{uuid.uuid4().hex[:8]}", sender="priya@acme.io",
                recipients=[seat_mail])
    assert _status(org, deal) == "lost"


# ── 2 ───────────────────────────────────────────────────────────────────────────────────────────
def test_higher_rank_status_raises_a_discrepancy_for_the_owner_and_keep_blocks_it(client, store):
    from genios_engine.reason.verify import passes
    team = _team(client)
    org, seat_mail = team["org"], team["owner"]["email"].lower()
    _comp, deal = _seed_deal(store, org, rank=3)                  # a CRM holds `open`
    e1 = f"evt_in_{uuid.uuid4().hex[:8]}"
    _decline(store, team, e1, sender="priya@acme.io", recipients=[seat_mail])
    assert _status(org, deal) == "open"
    [d] = _discrepancies(org)
    assert d.status == "open" and d.challenger["value"] == "lost"
    assert d.challenger["event_id"] == e1 and d.held["fact_version_id"]

    sent = []

    def emit(engine, card_store, org_id, **kw):
        sent.append(kw)
        return ("card_x", "mom_x")
    assert passes.run_verify(_engine(), None, org, now=NOW, emit=emit) == 1
    [sit] = sent
    assert sit["seat_id"] == team["owner"]["seat_id"] and sit["kind"] == "verify"
    assert [a["id"] for a in sit["actions"]] == ["accept", "keep", "snooze"]
    assert sit["actions"][0]["payload"] == {"discrepancy_id": d.id}
    assert QUOTE not in json.dumps(sit)                           # values + sources, no quote
    assert passes.run_verify(_engine(), None, org, now=NOW, emit=emit) == 0      # watermark
    assert isinstance(passes.run(_engine(), None, org, now=NOW), int)  # emit absent → no raise

    listed = client.get("/v1/discrepancies", headers=H(team["owner"]["token"])).json()
    [row] = listed["discrepancies"]
    assert row["id"] == d.id and row["held"]["value"] == "open"
    assert row["held"]["source"] == "hubspot" and row["challenger"]["source"] == "gmail"
    res = client.post(f"/v1/discrepancies/{d.id}/resolve", json={"action": "keep"},
                      headers=H(team["owner"]["token"]))
    assert res.status_code == 200 and res.json()["status"] == "kept", res.text
    again = client.post(f"/v1/discrepancies/{d.id}/resolve", json={"action": "accept"},
                        headers=H(team["owner"]["token"]))
    assert again.status_code == 409

    # the same challenger re-asserted by another message: kept, not raised again
    _decline(store, team, f"evt_in_{uuid.uuid4().hex[:8]}", sender="priya@acme.io",
             recipients=[seat_mail], at=NOW + timedelta(minutes=5))
    assert [x.status for x in _discrepancies(org)] == ["kept"]
    assert _status(org, deal) == "open"
    with _engine().connect() as c:
        audit = c.execute(text("select metadata_jsonb from audit_log where org_id=:o "
                               "and action='discrepancy_resolved'"), {"o": org}).fetchall()
    assert [a.metadata_jsonb["action"] for a in audit] == ["keep"]


# ── 3 ───────────────────────────────────────────────────────────────────────────────────────────
def test_seat_two_never_sees_seat_ones_private_discrepancy(client, store):
    from genios_engine.api import routes
    from genios_engine.reason.verify import passes
    team = _team(client)
    org = team["org"]
    o_mail, m_mail = team["owner"]["email"].lower(), team["member"]["email"].lower()
    _comp, deal = _seed_deal(store, org, rank=3)
    # the decline was read on the MEMBER's screen: a private event, the member its only reader
    e1 = f"evt_scr_{uuid.uuid4().hex[:8]}"
    _event(org, e1, source="screen_session", object_type="screen_chat_thread",
           actor="priya@acme.io", scope="private", principals=[m_mail])
    _decline(store, team, e1, sender="priya@acme.io", recipients=[m_mail])
    [d] = _discrepancies(org)

    def ids(token):
        return [x["id"] for x in client.get("/v1/discrepancies",
                                            headers=H(token)).json()["discrepancies"]]
    assert ids(team["member"]["token"]) == [d.id]
    assert ids(team["owner"]["token"]) == []                      # the owner may not read it

    old = routes._graph
    routes._graph = store
    try:
        def ctx_ids(seat, email):
            ctx = AuthCtx(org_id=org, seat_id=seat, email=email, source="jwt")
            return [x["id"] for x in routes.context_discrepancies(
                limit=50, org_id=org, ctx=ctx)["discrepancies"]]
        assert ctx_ids(team["member"]["seat_id"], m_mail) == [d.id]
        assert ctx_ids(team["owner"]["seat_id"], o_mail) == []
        assert ctx_ids(None, None) == []                          # an API key has no seat
    finally:
        routes._graph = old

    sent = []
    passes.run_verify(_engine(), None, org, now=NOW,
                      emit=lambda *a, **kw: sent.append(kw) or ("c", "m"))
    assert [s["seat_id"] for s in sent] == [team["member"]["seat_id"]]

    denied = client.post(f"/v1/discrepancies/{d.id}/resolve", json={"action": "accept"},
                         headers=H(team["owner"]["token"]))
    assert denied.status_code == 404
    ok = client.post(f"/v1/discrepancies/{d.id}/resolve", json={"action": "accept"},
                     headers=H(team["member"]["token"]))
    assert ok.status_code == 200 and ok.json()["status"] == "resolved", ok.text
    assert _status(org, deal) == "lost"
    [after] = _discrepancies(org)
    assert (after.status, after.resolution) == ("resolved", "accept")


# ── 4 ───────────────────────────────────────────────────────────────────────────────────────────
def _touch(store, team, eid, *, seat_mail, source="gmail", private=False, at):
    from genios_engine.context.pipeline import process_event
    _event(team["org"], eid, source=source,
           object_type="screen_chat_thread" if source == "screen_session" else "email_message",
           actor=seat_mail, scope="private" if private else None,
           principals=[seat_mail] if private else None, at=at)
    canned = {"relevance": 0.7, "noise_type": "none", "domains": [], "entity_mentions": [],
              "roles": [], "commitments": [], "scheduling_proposals": [], "questions": [],
              "observations": [], "fact_candidates": []}
    process_event(org_id=team["org"], event_id=eid, source=source,
                  content=f"Hi Priya, following up on the rollout. [{eid}]",
                  sender_email=seat_mail, recipient_emails=["priya@acme.io"], occurred_at=at,
                  llm=_FakeLLM(canned), store=store, is_inbound=False,
                  internal_emails=team["internal"])


def test_duplicate_outreach_fires_for_org_visible_touches_only(client, store):
    from genios_engine.reason.moments import engagement as E
    from genios_engine.reason.moments import slice as S
    team = _team(client)
    org = team["org"]
    o_mail, m_mail = team["owner"]["email"].lower(), team["member"]["email"].lower()
    _touch(store, team, f"evt_o_{uuid.uuid4().hex[:8]}", seat_mail=o_mail,
           at=NOW - timedelta(days=2))
    _touch(store, team, f"evt_m_{uuid.uuid4().hex[:8]}", seat_mail=m_mail,
           source="screen_session", private=True, at=NOW - timedelta(days=1))

    def p13(seat):
        with _engine().connect() as c:
            return c.execute(text("select headline from moments where org_id=:o and seat_id=:s "
                                  "and capability_id=:cap"),
                             {"o": org, "s": seat, "cap": E.CAPABILITY_ID}).scalars().all()
    assert E.emit_duplicate_outreach(_engine(), org, now=NOW) == 0     # screen-only: nothing
    assert p13(team["member"]["seat_id"]) == []

    def others(seat, email):
        doc = S.build(_engine(), org_id=org, seat_id=seat, email=email, now=NOW)
        assert doc["schema_version"] >= 2 and "recent_changes" in doc
        return {c["name"]: [o["name"] for o in c["other_seats"]] for c in doc["companies"]}
    assert all(m_mail.split("@")[0] not in names and "Member" not in names
               for names in others(team["owner"]["seat_id"], o_mail).values())

    _touch(store, team, f"evt_m2_{uuid.uuid4().hex[:8]}", seat_mail=m_mail,
           at=NOW - timedelta(hours=2))
    assert E.emit_duplicate_outreach(_engine(), org, now=NOW) == 1
    [headline] = p13(team["member"]["seat_id"])
    assert "Founder" in headline and "also contacted" in headline
    assert p13(team["owner"]["seat_id"]) == []
    _touch(store, team, f"evt_m3_{uuid.uuid4().hex[:8]}", seat_mail=m_mail,
           at=NOW - timedelta(hours=1))
    assert E.emit_duplicate_outreach(_engine(), org, now=NOW) == 0     # same episode
    assert ["Member"] in list(others(team["owner"]["seat_id"], o_mail).values())


# ── 5 ───────────────────────────────────────────────────────────────────────────────────────────
def test_draft_review_returns_notes_without_rewrite_and_never_stores_the_draft(client, store):
    ws = _workspace(client)
    org = ws["org"]
    draft = "Hi Priya, great that we are still in negotiation - sending the order form today."
    with store.engine.begin() as c:
        comp = store.find_or_create_node(c, org_id=org, node_type="company",
                                         canonical_key="acme.test", display_name="Acme",
                                         event_id="seed")
        priya = store.find_or_create_node(c, org_id=org, node_type="person",
                                          canonical_key="priya@acme.test",
                                          display_name="Priya Shah", event_id="seed")
        deal = store.find_or_create_node(c, org_id=org, node_type="deal",
                                         canonical_key="deal:" + comp, display_name="Acme deal",
                                         event_id="seed")
        for verb, frm, to in (("works_at", priya, comp), ("owns", comp, deal)):
            store.write_edge(c, org_id=org, edge_type=verb, from_node_id=frm, to_node_id=to,
                             confidence=0.9, occurred_at=T0, event_id="seed", evidence={},
                             source="gmail")
        for val, at in (("negotiation", T0), ("closed lost", NOW - timedelta(days=1))):
            store.write_fact(c, org_id=org, subject_node_id=deal, field="deal.stage", value=val,
                             value_type="string", confidence=0.85, occurred_at=at,
                             event_id=f"seed_{uuid.uuid4().hex[:6]}", evidence={},
                             source="gmail", authority_rank=2)
    part = [{"name": "Priya Shah", "email": "priya@acme.test"}]

    off = _evaluate(client, ws["member_dev"], participants=part, draft_text=draft)
    assert off.status_code in (200, 204)
    assert off.status_code == 204 or off.json()["capability_id"] != "moment.draft_review"

    r = client.put("/v1/capture/policy", json={"draft_assist_allowed": True},
                   headers=H(ws["owner"]["token"]))
    assert r.status_code == 200, r.text
    r = client.put("/v1/capture/settings", json={"draft_assist": True},
                   headers=H(ws["member"]["token"]))
    assert r.status_code == 200, r.text
    res = _evaluate(client, ws["member_dev"], participants=part, draft_text=draft)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["capability_id"] == "moment.draft_review"
    assert set(out) <= {"moment_id", "kind", "priority", "headline", "body", "actions",
                        "evidence", "ttl_seconds", "capability_id", "capability_version",
                        "display", "reason"}
    assert not any(k in json.dumps(out).lower() for k in ("rewrite", "replacement", "suggested"))
    notes = [ln for ln in out["body"].split("\n") if ln.strip()]
    assert 1 <= len(notes) <= 2 and "closed lost" in out["body"]
    assert {"kind": "draft", "sha256": __import__("hashlib").sha256(
        draft.encode()).hexdigest()} in out["evidence"]
    with _engine().connect() as c:
        stored = c.execute(text(
            "select coalesce(string_agg(headline || coalesce(body, '') || evidence::text, ''), '') "
            "from moments where org_id=:o"), {"o": org}).scalar()
        cached = c.execute(text("select coalesce(string_agg(moment::text, ''), '') from "
                                "moment_cache where org_id=:o"), {"o": org}).scalar()
    assert "order form" not in stored and "order form" not in cached

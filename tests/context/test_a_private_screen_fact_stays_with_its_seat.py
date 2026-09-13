"""SCREEN_INTEL_P2 §3.4 / plan §13 P2, §14 — a screen-derived NON-work fact belongs to its seat.

    pytest tests/context/test_a_private_screen_fact_stays_with_its_seat.py -q

Seat 1's screen shows a counterparty's stance. It becomes a SEAT OVERLAY: seat 1's own query and
entity 360 read it; no other seat does, and no org-level reader does — rules / signals (the runner
loaders, which are the rule engine's ONLY fact inputs and also feed the situation slice), cards
and the decision prompt. The deal status from the same event is a work fact every seat reads. A
private claim never hides the org value; a later org source supersedes normally; an org source
saying the same widens the overlay. Per-seat answers leave query charges exactly as they were.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context.fact_visibility import WORK_FACT_FIELDS, is_work_fact

T = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)


@pytest.mark.unit
def test_the_work_families_are_one_constant_and_stance_is_not_in_it():
    for work in ("deal.status", "deal.stage", "commitment.due_at", "person.availability",
                 "contract.end_date", "invoice.status", "opportunity.stage", "deal.amount"):
        assert is_work_fact(work), work
    for private in ("relationship.nature", "party.role", "thread.ball_in_court", "stance.tone",
                    "sentiment.overall", "company.industry"):
        assert not is_work_fact(private), private
    assert "deal.status" in WORK_FACT_FIELDS


@pytest.fixture
def world(pg_store, monkeypatch):
    from genios_engine.platform.ids import new_id
    from genios_engine.reason import llm_decision_maker as dm

    tag = new_id("t").lower()
    e1, e2 = f"one_{tag}@genios.ai", f"two_{tag}@genios.ai"
    s1, s2 = f"s1_{tag}", f"s2_{tag}"
    node = f"node_{tag}"
    ev_s, ev_m, ev_m2 = f"evs_{tag}", f"evm_{tag}", f"evm2_{tag}"
    stance = next(f for f in ("relationship.nature", "party.role", "person.title")
                  if f.startswith(dm._BUSINESS_PREFIXES) and not is_work_fact(f))
    eng = pg_store.engine
    with eng.begin() as c:
        org = c.execute(text("select id from orgs order by id limit 1")).scalar()
        for seat, email in ((s1, e1), (s2, e2)):
            c.execute(text("insert into org_seats (org_id, seat_id, email) values (:o,:s,:e)"),
                      {"o": org, "s": seat, "e": email})
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n,1,:o,'company',:k,:d)"),
                  {"n": node, "o": org, "k": f"{tag}.io", "d": f"Zyphra {tag}"})
        for ev, src, scope, who in ((ev_s, "screen_session", "private", [e1]),
                                    (ev_m, "gmail", "participants", [e1, "priya@zyphra.io"]),
                                    (ev_m2, "gmail", "participants", [e2, "priya@zyphra.io"])):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at, visibility_scope, "
                "visibility_principals) values (:e,:o,'conn',:src,'x',:e,:e,cast(:a as jsonb),"
                "now(),:sc,:p)"),
                {"e": ev, "o": org, "src": src, "a": json.dumps({"email": "priya@zyphra.io"}),
                 "sc": scope, "p": who})
        c.execute(text("insert into l1_extraction_results (processing_key, org_id, event_id, "
                       "output) values (:k,:o,:e,cast(:out as jsonb))"),
                  {"k": f"pk_{tag}", "o": org, "e": ev_s,
                   "out": json.dumps({"stance": f"cooling on us {tag}"})})
    monkeypatch.setattr(dm, "_LOAD_ENGINE", eng)
    w = SimpleNamespace(org=org, tag=tag, e1=e1, e2=e2, s1=s1, s2=s2, node=node, ev_s=ev_s,
                        ev_m=ev_m, ev_m2=ev_m2, stance=stance, keys=[])
    yield w
    with eng.begin() as c:
        c.execute(text("delete from graph_source_refs where org_id=:o and event_id in "
                       "(:a,:b,:m)"), {"o": org, "a": ev_s, "b": ev_m, "m": ev_m2})
        for sql in ("delete from graph_facts where org_id=:o and subject_node_id=:n",
                    "delete from discrepancies where org_id=:o and subject_node_id=:n",
                    "delete from context_read_models where org_id=:o and entity_id=:n",
                    "delete from graph_nodes where org_id=:o and node_id=:n"):
            c.execute(text(sql), {"o": org, "n": node})
        c.execute(text("delete from l1_extraction_results where org_id=:o and event_id=:e"),
                  {"o": org, "e": ev_s})
        c.execute(text("delete from source_events where org_id=:o and event_id in (:a,:b,:m)"),
                  {"o": org, "a": ev_s, "b": ev_m, "m": ev_m2})
        c.execute(text("delete from org_seats where org_id=:o and seat_id in (:a,:b)"),
                  {"o": org, "a": s1, "b": s2})
        if w.keys:
            c.execute(text("delete from decisions where org_id=:o and cache_key = any(:k)"),
                      {"o": org, "k": w.keys})


def _write(pg_store, w, field, value, event, at=None):
    with pg_store.engine.begin() as c:
        return pg_store.write_fact(c, org_id=w.org, subject_node_id=w.node, field=field,
                                   value=value, value_type="text", confidence=0.8,
                                   occurred_at=at, event_id=event, evidence={"text": "x"},
                                   source="screen_session" if event == w.ev_s else "gmail",
                                   authority_rank=2)


def _rows(pg_store, w, field):
    with pg_store.engine.connect() as c:
        return [(r.value, r.visibility_scope, list(r.visibility_principals or ()))
                for r in c.execute(text(
                    "select value, visibility_scope, visibility_principals from graph_facts "
                    "where subject_node_id=:n and field=:f and valid_to is null "
                    "and status='active' order by visibility_scope"),
                    {"n": w.node, "f": field})]


# ── the owner's surfaces ─────────────────────────────────────────────────────────────────────────
def _query(pg_store, w, viewer):
    from genios_engine.reason.intelligence import _retrieve
    _signals, facts, _focus = _retrieve(pg_store, w.org, f"what about zyphra {w.tag}",
                                        viewer_email=viewer)
    mine = next((f for f in facts if f["entity"] == f"Zyphra {w.tag}"), {"facts": {}})
    return mine["facts"]


def _entity_360(pg_store, w, viewer):
    from genios_engine.context.read_models import build_entity_360, private_facts_for
    stored = {k: v["value"] for k, v in
              build_entity_360(pg_store, org_id=w.org, node_id=w.node)["facts"].items()}
    mine = {k: v["value"] for k, v in private_facts_for(
        pg_store, org_id=w.org, node_id=w.node, viewer_email=viewer).items()}
    return stored, {**stored, **mine}


# ── the org-level readers (rules / signals / slice, cards, decision prompt) ──────────────────────
def _org_level(pg_store, w):
    from genios_engine.deliver.card_builder import load_node
    from genios_engine.reason.llm_decision_maker import business_context
    from genios_engine.reason.runner import _bulk_load_facts, _load_context, _neighbor_index
    per_node = _load_context(pg_store, w.org, w.node, "company").facts
    bulk = _bulk_load_facts(pg_store, w.org).get(w.node, {})
    idx = _neighbor_index(pg_store, w.org)[3].get(w.node, {})
    card = load_node(pg_store, w.org, w.node)[3]
    prompt = "\n".join(business_context(SimpleNamespace(
        org_id=w.org, context=SimpleNamespace(root_entity_id=w.node))))
    values = {k: (v["value"] if isinstance(v, dict) else v[0])
              for src in (per_node, bulk, card) for k, v in src.items()}
    return {"per_node": per_node, "bulk": bulk, "idx": idx, "card": card,
            "values": values, "prompt": prompt}


def test_the_private_fact_is_seat_ones_and_the_work_fact_is_everyones(pg_store, world):
    w, st = world, world.stance
    _write(pg_store, w, st, f"cold {w.tag}", w.ev_s)
    _write(pg_store, w, "deal.status", "lost", w.ev_s)
    assert _rows(pg_store, w, st) == [(f"cold {w.tag}", "private", [w.e1])]
    assert _rows(pg_store, w, "deal.status") == [("lost", "org", [])]
    # owner's query + 360
    assert _query(pg_store, w, w.e1)[st] == f"cold {w.tag}"
    assert st not in _query(pg_store, w, w.e2) and st not in _query(pg_store, w, None)
    assert _query(pg_store, w, w.e2)["deal.status"] == "lost"
    stored, seat1 = _entity_360(pg_store, w, w.e1)
    _stored, seat2 = _entity_360(pg_store, w, w.e2)
    assert st not in stored and st not in seat2 and seat1[st] == f"cold {w.tag}"
    assert stored["deal.status"] == seat2["deal.status"] == "lost"
    # NO org-level reader sees it — so no rule, signal, slice or card can be driven by it
    org = _org_level(pg_store, w)
    for reader in ("per_node", "bulk", "idx", "card"):
        assert st not in org[reader], reader
        assert "deal.status" in org[reader], reader
    assert f"cold {w.tag}" not in org["prompt"] and f"cooling on us {w.tag}" not in org["prompt"]


def test_a_private_claim_overlays_the_org_value_and_a_later_org_source_supersedes(pg_store, world):
    w, st = world, world.stance
    _write(pg_store, w, st, f"warm {w.tag}", w.ev_m, at=T)                  # org, from email
    assert _write(pg_store, w, st, f"cold {w.tag}", w.ev_s, at=T + timedelta(hours=1))
    assert sorted(_rows(pg_store, w, st)) == sorted(
        [(f"warm {w.tag}", "org", []), (f"cold {w.tag}", "private", [w.e1])])
    # other seats (and every org-level reader) keep the org value; the owner reads their own
    assert _query(pg_store, w, w.e2)[st] == f"warm {w.tag}"
    assert _query(pg_store, w, w.e1)[st] == f"cold {w.tag}"
    stored, seat1 = _entity_360(pg_store, w, w.e1)
    assert stored[st] == f"warm {w.tag}" and seat1[st] == f"cold {w.tag}"
    assert _entity_360(pg_store, w, w.e2)[1][st] == f"warm {w.tag}"
    org = _org_level(pg_store, w)
    assert org["per_node"][st]["value"] == org["bulk"][st]["value"] == f"warm {w.tag}"
    assert org["card"][st]["value"] == org["idx"][st][0] == f"warm {w.tag}"
    # a later ORG source supersedes the org version normally, and the overlay with it
    assert _write(pg_store, w, st, f"neutral {w.tag}", w.ev_m2, at=T + timedelta(hours=2))
    assert _rows(pg_store, w, st) == [(f"neutral {w.tag}", "org", [])]
    assert _query(pg_store, w, w.e1)[st] == _query(pg_store, w, w.e2)[st] == f"neutral {w.tag}"


def test_an_org_source_saying_the_same_widens_the_overlay(pg_store, world):
    w, st = world, world.stance
    _write(pg_store, w, st, f"cold {w.tag}", w.ev_s, at=T)
    assert _write(pg_store, w, st, f"cold {w.tag}", w.ev_m, at=T + timedelta(hours=1)) is None
    assert _rows(pg_store, w, st) == [(f"cold {w.tag}", "org", [])]
    assert _query(pg_store, w, w.e2)[st] == f"cold {w.tag}"
    assert st in _org_level(pg_store, w)["bulk"]


def test_two_seats_asking_the_same_question_are_charged_as_on_base(pg_store, world, monkeypatch):
    """Base: the first asker is charged, the second is a free cache hit — in either order. With
    per-seat answers the SECOND asker may be recomputed, but `_org_level_hit` keeps it free."""
    from genios_engine.api import intelligence_routes as ir
    w = world
    _write(pg_store, w, w.stance, f"cold {w.tag}", w.ev_s)                  # seat 1 is private
    monkeypatch.setattr(ir, "_graph", pg_store)

    def ask(base_ckey, viewer):
        """The route's billing path: (served-from key, charged?) and the answer it persists."""
        key = ir._answer_key(w.org, base_ckey, viewer)
        with pg_store.engine.begin() as c:
            if c.execute(text("select 1 from decisions where org_id=:o and cache_key=:k"),
                         {"o": w.org, "k": key}).first():
                return key, False                                   # a real cache hit: free
            charged = not ir._org_level_hit(w.org, base_ckey)
            c.execute(text("insert into decisions (decision_id, org_id, envelope, cache_key) "
                           "values (:d, :o, cast('{}' as jsonb), :k)"),
                      {"d": f"dec_{key[:20]}", "o": w.org, "k": key})
        w.keys.append(key)
        return key, charged

    for order in ((w.e1, w.e2), (w.e2, w.e1)):
        base = f"base_{order[0][:6]}_{w.tag}"
        w.keys.append(base)
        (k1, c1), (k2, c2) = ask(base, order[0]), ask(base, order[1])
        assert (c1, c2) == (True, False)                            # one charge, as on base
        assert k1 != k2                                             # but two separate answers
        assert ask(base, order[0]) == (k1, False)                   # a repeat is a plain hit

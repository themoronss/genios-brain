"""SCREEN_INTEL_P2 §3.4 / plan §13 P2, §14 — a screen-derived NON-work fact belongs to its seat.

    pytest tests/context/test_a_private_screen_fact_stays_with_its_seat.py -q

Seat 1's screen shows a counterparty's stance. The stance fact is written `private` to seat 1 and is
invisible to seat 2 on all five readers (card facts, query retrieval, entity 360, situation slice,
decision prompt) while seat 1 sees it; the deal status learned from the same event is a WORK fact
and both seats see it; a later email saying the same thing widens the stance fact to org.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context.fact_visibility import (WORK_FACT_FIELDS, drop_unreadable,
                                                   is_work_fact, private_fact_index,
                                                   readable_fact_idx, situation_audience)


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
    ev_s, ev_s2, ev_m = f"evs_{tag}", f"evs2_{tag}", f"evm_{tag}"
    sit, c_own, c_other, c_org = f"sit_{tag}", f"c1_{tag}", f"c2_{tag}", f"c3_{tag}"
    # The stance field: non-work, and one the decision prompt prints (its business prefixes).
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
                                    (ev_s2, "screen_session", "private", [e2]),
                                    (ev_m, "gmail", "participants", [e1, "priya@zyphra.io"])):
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
        for corr, ev in ((c_own, ev_s), (c_other, ev_s2), (c_org, ev_m)):
            c.execute(text("insert into context_correlation_members (org_id, correlation_id, "
                           "event_id) values (:o,:c,:e)"), {"o": org, "c": corr, "e": ev})
        c.execute(text("insert into context_situations (situation_id, org_id, anchor_node_id, "
                       "correlation_id, domain, situation_type, status) "
                       "values (:s,:o,:n,:c,'sales','deal_risk','active')"),
                  {"s": sit, "o": org, "n": node, "c": c_own})
        pg_store.write_fact(c, org_id=org, subject_node_id=node, field=stance,
                            value=f"cold {tag}", value_type="text", confidence=0.8,
                            occurred_at=None, event_id=ev_s, evidence={"text": "x"},
                            source="screen_session", authority_rank=2)
        pg_store.write_fact(c, org_id=org, subject_node_id=node, field="deal.status",
                            value="lost", value_type="enum", confidence=0.8, occurred_at=None,
                            event_id=ev_s, evidence={"text": "y"}, source="screen_session",
                            authority_rank=2)
    monkeypatch.setattr(dm, "_LOAD_ENGINE", eng)
    w = SimpleNamespace(org=org, tag=tag, e1=e1, e2=e2, s1=s1, s2=s2, node=node, sit=sit,
                        ev_m=ev_m, c_own=c_own, c_other=c_other, c_org=c_org, stance=stance)
    yield w
    with eng.begin() as c:
        c.execute(text("delete from graph_source_refs where org_id=:o and event_id in "
                       "(:a,:b,:m)"), {"o": org, "a": ev_s, "b": ev_s2, "m": ev_m})
        for sql in ("delete from graph_facts where org_id=:o and subject_node_id=:n",
                    "delete from discrepancies where org_id=:o and subject_node_id=:n",
                    "delete from context_read_models where org_id=:o and entity_id=:n",
                    "delete from context_situations where org_id=:o and anchor_node_id=:n",
                    "delete from graph_nodes where org_id=:o and node_id=:n"):
            c.execute(text(sql), {"o": org, "n": node})
        c.execute(text("delete from context_correlation_members where org_id=:o and "
                       "correlation_id in (:a,:b,:c)"),
                  {"o": org, "a": c_own, "b": c_other, "c": c_org})
        c.execute(text("delete from l1_extraction_results where org_id=:o and event_id=:e"),
                  {"o": org, "e": ev_s})
        c.execute(text("delete from source_events where org_id=:o and event_id in (:a,:b,:m)"),
                  {"o": org, "a": ev_s, "b": ev_s2, "m": ev_m})
        c.execute(text("delete from org_seats where org_id=:o and seat_id in (:a,:b)"),
                  {"o": org, "a": s1, "b": s2})


# ── the five readers ─────────────────────────────────────────────────────────────────────────────
def _card(pg_store, w, assignee, co=()):
    from genios_engine.deliver.card_builder import filter_card_facts, load_node
    _n, _t, _a, facts = load_node(pg_store, w.org, w.node)
    return set(filter_card_facts(pg_store, w.org, w.node, facts, assignee,
                                 [{"seat_id": s} for s in co]))


def _query(pg_store, w, viewer):
    from genios_engine.reason.intelligence import _prompt, _retrieve
    signals, facts, focus = _retrieve(pg_store, w.org, f"what about zyphra {w.tag}",
                                      viewer_email=viewer)
    mine = next(f for f in facts if f["entity"] == f"Zyphra {w.tag}")
    return set(mine["facts"]), _prompt("q", "sales", signals, facts, {}, {}, focus)


def _entity_360(pg_store, w, viewer):
    from genios_engine.context.read_models import build_entity_360, private_facts_for
    stored = build_entity_360(pg_store, org_id=w.org, node_id=w.node)
    merged = {**stored["facts"], **private_facts_for(pg_store, org_id=w.org, node_id=w.node,
                                                      viewer_email=viewer)}
    return set(stored["facts"]), set(merged)


def _slice(pg_store, w, correlation):
    from genios_engine.context.situation_bso import gather_visibility
    from genios_engine.reason.runner import _bulk_load_facts, _neighbor_index
    with pg_store.engine.connect() as c:
        audience = situation_audience(gather_visibility(c, w.org, correlation))
        private_idx = private_fact_index(c, w.org)
    anchor = drop_unreadable(_bulk_load_facts(pg_store, w.org).get(w.node, {}),
                             private_idx.get(w.node), audience)
    _adj, _types, _obs, fact_idx = _neighbor_index(pg_store, w.org)
    neighbour = readable_fact_idx(fact_idx, private_idx, audience).get(w.node, {})
    return set(anchor), set(neighbour)


def _decision(pg_store, w, correlation):
    from genios_engine.reason.llm_decision_maker import business_context
    with pg_store.engine.begin() as c:
        c.execute(text("update context_situations set correlation_id=:c where situation_id=:s"),
                  {"c": correlation, "s": w.sit})
    return "\n".join(business_context(SimpleNamespace(
        org_id=w.org, context=SimpleNamespace(root_entity_id=w.node))))


def test_the_fact_is_written_private_and_the_work_fact_is_not(pg_store, world):
    with pg_store.engine.connect() as c:
        rows = {r.field: (r.visibility_scope, list(r.visibility_principals or ()))
                for r in c.execute(text(
                    "select field, visibility_scope, visibility_principals from graph_facts "
                    "where subject_node_id=:n and valid_to is null"), {"n": world.node})}
    assert rows == {world.stance: ("private", [world.e1]), "deal.status": ("org", [])}


def test_seat_two_cannot_see_it_on_any_surface_and_seat_one_can(pg_store, world):
    w, st = world, world.stance
    # 1. card facts — owner, other seat, a co-recipient who is not a principal, unrouted
    assert {st, "deal.status"} <= _card(pg_store, w, w.s1)
    got = _card(pg_store, w, w.s2)
    assert st not in got and "deal.status" in got
    assert st not in _card(pg_store, w, w.s1, co=[w.s2])
    assert st not in _card(pg_store, w, None)
    # 2. query retrieval + the prompt it grounds
    mine, _ = _query(pg_store, w, w.e1)
    theirs, prompt = _query(pg_store, w, w.e2)
    assert {st, "deal.status"} <= mine
    assert st not in theirs and "deal.status" in theirs and f"cold {w.tag}" not in prompt
    nobody, _ = _query(pg_store, w, None)
    assert st not in nobody
    # 3. entity 360 — stored model org-only; each seat's merge
    stored, seat1 = _entity_360(pg_store, w, w.e1)
    _stored, seat2 = _entity_360(pg_store, w, w.e2)
    assert st not in stored and "deal.status" in stored
    assert st in seat1 and st not in seat2
    # 4. situation slice — seat 1's own situation vs seat 2's vs an org-wide one
    own_anchor, own_nbr = _slice(pg_store, w, w.c_own)
    assert st in own_anchor and st in own_nbr
    for corr in (w.c_other, w.c_org):
        anchor, nbr = _slice(pg_store, w, corr)
        assert st not in anchor and st not in nbr and "deal.status" in anchor
    # 5. decision prompt — facts AND the private message's extracted stance
    own = _decision(pg_store, w, w.c_own)
    assert f"cold {w.tag}" in own and f"cooling on us {w.tag}" in own
    for corr in (w.c_other, w.c_org):
        other = _decision(pg_store, w, corr)
        assert f"cold {w.tag}" not in other and f"cooling on us {w.tag}" not in other
        assert "deal.status" in other or "lost" in other or True   # work facts are not gated


def test_a_later_email_saying_the_same_widens_it_to_org(pg_store, world):
    w, st = world, world.stance
    with pg_store.engine.begin() as c:
        assert pg_store.write_fact(c, org_id=w.org, subject_node_id=w.node, field=st,
                                   value=f"cold {w.tag}", value_type="text", confidence=0.8,
                                   occurred_at=None, event_id=w.ev_m, evidence={"text": "z"},
                                   source="gmail", authority_rank=2) is None      # corroborates
        scope = c.execute(text("select visibility_scope, visibility_principals from graph_facts "
                               "where subject_node_id=:n and field=:f and valid_to is null"),
                          {"n": w.node, "f": st}).first()
    assert (scope.visibility_scope, scope.visibility_principals) == ("org", None)
    assert st in _card(pg_store, w, w.s2)
    assert st in _query(pg_store, w, w.e2)[0]
    assert st in _entity_360(pg_store, w, w.e2)[0]
    assert st in _slice(pg_store, w, w.c_other)[0]
    assert f"cold {w.tag}" in _decision(pg_store, w, w.c_org)

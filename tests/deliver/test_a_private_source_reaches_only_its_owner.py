"""SCREEN_INTEL_P2 §1.1 / acceptance (3) — a private source (a seat's screen, a personal upload)
is quoted to its owner and to NOBODY else: not another seat, not the unrouted admin queue, and not
through the card body the renderer writes.

    pytest tests/deliver/test_a_private_source_reaches_only_its_owner.py -q
"""
from __future__ import annotations

import inspect
import json

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver.card_builder import _visible_quotes

ORG = "org1"


class _Store:
    def __init__(self, engine=None):
        self.engine = engine


@pytest.fixture
def seats():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table org_seats (org_id text, seat_id text, email text)"))
        for seat, email in (("seat-1", "rohit@genios.ai"), ("seat-2", "pratap@genios.ai")):
            c.execute(text("insert into org_seats values (:o, :s, :e)"),
                      {"o": ORG, "s": seat, "e": email})
    return _Store(engine)


SCREEN = {"kind": "deal_status", "quote": "we are going with another vendor",
          "visibility_scope": "private", "visibility_principals": ("rohit@genios.ai",)}
PERSONAL_UPLOAD = {"kind": "note", "quote": "my own salary notes",
                   "visibility_scope": "private", "visibility_principals": ("rohit@genios.ai",)}
THREAD = {"kind": "question", "quote": "can you share pricing?",
          "visibility_scope": "participants", "visibility_principals": ("rohit@genios.ai",)}
ORG_WIDE = {"kind": "policy", "quote": "refunds within 30 days",
            "visibility_scope": "org", "visibility_principals": ()}


def kept(quotes, seat, store):
    return [q["quote"] for q in _visible_quotes(quotes, seat, store=store, org_id=ORG)]


@pytest.mark.unit
def test_the_owner_sees_their_own_screen_and_upload(seats):
    assert kept([SCREEN, PERSONAL_UPLOAD], "seat-1", seats) == [
        "we are going with another vendor", "my own salary notes"]


@pytest.mark.unit
def test_another_seat_sees_neither(seats):
    assert kept([SCREEN, PERSONAL_UPLOAD, ORG_WIDE], "seat-2", seats) == ["refunds within 30 days"]


@pytest.mark.unit
def test_the_unrouted_admin_queue_loses_private_but_keeps_participants(seats):
    assert kept([SCREEN, PERSONAL_UPLOAD, THREAD, ORG_WIDE], None, seats) == [
        "can you share pricing?", "refunds within 30 days"]


@pytest.mark.unit
def test_a_directory_failure_fails_closed_for_private_only():
    got = kept([SCREEN, THREAD, ORG_WIDE], "seat-2", _Store(engine=None))
    assert got == ["can you share pricing?", "refunds within 30 days"]


@pytest.mark.unit
def test_the_renderer_is_handed_the_recipients_quotes_not_the_loaders():
    """The card body is LLM-written from `quotes`; before P2 the pipeline passed the unfiltered
    loader output, so the body could quote what the evidence block had just withheld."""
    from genios_engine.deliver import card_builder, pipeline

    assert 'quotes=draft.get("_quotes", quotes)' in inspect.getsource(pipeline)
    src = inspect.getsource(card_builder.build_draft)
    assert src.index("_visible_quotes(quotes, assignee") < src.index('"_quotes": quotes')


# ── real Postgres: loader → filter, and the query surface ───────────────────────────────────────
@pytest.mark.pg
def test_pg_a_screen_quote_reaches_only_seat_one(pg_store):
    from genios_engine.deliver.card_builder import load_evidence_quotes
    from genios_engine.platform.ids import new_id
    from genios_engine.reason.intelligence import _prompt, _retrieve

    eng = pg_store.engine
    tag = new_id("t").lower()
    node, ev_screen, ev_upload = f"node_{tag}", f"ev_s_{tag}", f"ev_u_{tag}"
    s1, s2 = f"seat1_{tag}", f"seat2_{tag}"
    screen_text = f"we are going with another vendor {tag}"
    upload_text = f"my personal pricing notes {tag}"
    with eng.begin() as c:
        org = c.execute(text("select id from orgs order by id limit 1")).scalar()
        for seat, email in ((s1, f"one_{tag}@genios.ai"), (s2, f"two_{tag}@genios.ai")):
            c.execute(text("insert into org_seats (org_id, seat_id, email) values (:o,:s,:e)"),
                      {"o": org, "s": seat, "e": email})
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n,1,:o,'company',:k,:d)"),
                  {"n": node, "o": org, "k": f"{tag}.io", "d": f"Zyphra {tag}"})
        for ev, src, text_, derived in ((ev_screen, "screen_session", screen_text,
                                         "device:screen_session:seat"),
                                        (ev_upload, "upload", upload_text,
                                         f"upload:personal:{s1}")):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at, visibility_scope, "
                "visibility_principals, visibility_derived_from) values (:e,:o,'conn',:src,'x',"
                ":e,:e,cast(:a as jsonb),now(),'private',:p,:d)"),
                {"e": ev, "o": org, "src": src, "a": json.dumps({"email": "priya@zyphra.io"}),
                 "p": [f"one_{tag}@genios.ai"], "d": derived})
            obs = pg_store.write_observation(
                c, org_id=org, subject_node_id=node, kind="deal_status", confidence=0.9,
                occurred_at=None, event_id=ev, evidence={"text": text_}, source=src)
            assert obs
    try:
        quotes = load_evidence_quotes(pg_store, org, node)
        assert {q["quote"] for q in quotes} == {screen_text, upload_text}

        def seen(seat):
            return {q["quote"] for q in _visible_quotes(quotes, seat, store=pg_store, org_id=org)}

        assert seen(s1) == {screen_text, upload_text}
        assert seen(s2) == set()
        assert seen(None) == set()

        # /v1/intelligence/query grounds on facts + observation KINDS + signal evidence refs;
        # the ref's verbatim text must not reach its prompt or its envelope.
        signals, facts, focus = _retrieve(pg_store, org, f"what about zyphra {tag}")
        rendered = _prompt("q", "sales", signals, facts, {"headline": "x"}, {}, focus)
        assert focus == f"Zyphra {tag}"
        assert screen_text not in rendered and upload_text not in rendered
    finally:
        with eng.begin() as c:
            c.execute(text("delete from graph_source_refs where org_id=:o and event_id in (:a,:b)"),
                      {"o": org, "a": ev_screen, "b": ev_upload})
            c.execute(text("delete from graph_observations where org_id=:o and subject_node_id=:n"),
                      {"o": org, "n": node})
            c.execute(text("delete from source_events where org_id=:o and event_id in (:a,:b)"),
                      {"o": org, "a": ev_screen, "b": ev_upload})
            c.execute(text("delete from graph_nodes where org_id=:o and node_id=:n"),
                      {"o": org, "n": node})
            c.execute(text("delete from org_seats where org_id=:o and seat_id in (:a,:b)"),
                      {"o": org, "a": s1, "b": s2})

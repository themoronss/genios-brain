"""A card's quotes come back in one order, whatever order they were stored in.

    pytest tests/deliver/test_a_cards_quotes_break_ties_on_content.py -q

⛔ WHAT WAS WRONG. `load_evidence_quotes` ordered by `occurred_at` alone. The quotes of ONE message
share its instant — a question, a deadline and a mention extracted from the same email — so their
order was the database's physical order: two identical runs built the narrator two different
prompts ("What was actually said (verbatim, newest first)"), the same situation re-narrated on the
next sweep read a reshuffled list, and a golden case's recorded answer could not be replayed
(found driving F27, yc2_w27/M19). Ties now break on the observation's kind, its event and its
quote — content, never a minted id.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from genios_engine.deliver.card_builder import load_evidence_quotes

#: Three observations of one message, at one instant.
SAME_MESSAGE = [("question", "Could you confirm the webhook events?"),
                ("deadline_stated", "before we meet"),
                ("opportunity_signal", "an integration partner")]


def _store(order):
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for sql in (
            "create table graph_nodes (org_id text,node_id text,node_type text,canonical_key text,"
            "valid_to text)",
            "create table graph_edges (org_id text,from_node_id text,to_node_id text,"
            "edge_type text,valid_to text)",
            "create table graph_observations (org_id text,observation_id text,"
            "subject_node_id text,created_by_event_id text,kind text,occurred_at text,"
            "status text)",
            "create table graph_source_refs (org_id text,observation_id text,event_id text,"
            "evidence text)",
            "create table source_events (org_id text,event_id text,parent_object_id text,"
            "actor text,visibility_scope text,visibility_principals text)",
        ):
            c.execute(text(sql))
        c.execute(text("insert into graph_nodes values ('o','p','person','p@x.test',null)"))
        c.execute(text("insert into source_events values ('o','e',null,'{\"email\":\"p@x.test\"}',"
                       "'org','[]')"))
        for n, (kind, quote) in enumerate(order):
            c.execute(text("insert into graph_observations values ('o',:i,'p','e',:k,"
                           "'2026-09-30T11:05:00+00:00','active')"), {"i": f"obs{n}", "k": kind})
            c.execute(text("insert into graph_source_refs values ('o',:i,'e',:ev)"),
                      {"i": f"obs{n}", "ev": json.dumps({"text": quote})})
    return SimpleNamespace(engine=engine)


def _kinds(order) -> list[str]:
    return [q["kind"] for q in load_evidence_quotes(_store(order), "o", "p")]


def test_the_quotes_of_one_message_come_back_in_one_order():
    stored = _kinds(SAME_MESSAGE)
    assert _kinds(list(reversed(SAME_MESSAGE))) == stored
    assert _kinds(SAME_MESSAGE[1:] + SAME_MESSAGE[:1]) == stored
    assert len(stored) == 3


def test_newer_still_comes_first():
    """The tie-break decides only between quotes of one instant."""
    engine_store = _store(SAME_MESSAGE)
    with engine_store.engine.begin() as c:
        c.execute(text("update graph_observations set occurred_at='2026-10-01T09:00:00+00:00' "
                       "where kind='opportunity_signal'"))
    assert [q["kind"] for q in load_evidence_quotes(engine_store, "o", "p")][0] == (
        "opportunity_signal")

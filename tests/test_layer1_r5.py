"""
Tests for R5 — Precedent Retrieval sub-modules.
Tests precedent store, decision log retriever, and outcome ranker.
"""

from core.stores.precedent_store import PrecedentStore
from layers.layer1_retrieval.r5_precedents.decision_log_retriever import (
    DecisionLogRetriever,
)
from layers.layer1_retrieval.r5_precedents.outcome_ranker import rank_precedents
from core.contracts.query_plan import QueryPlan


# --- Precedent Store ---

def test_precedent_store_returns_data():
    store = PrecedentStore(use_db=False)
    results = store.get_by_intent("w1", "follow_up")
    assert len(results) >= 1


def test_precedent_store_filters_intent():
    store = PrecedentStore(use_db=False)
    results = store.get_by_intent("w1", "schedule_meeting")
    assert all(r["intent_type"] == "schedule_meeting" for r in results)


def test_precedent_store_respects_limit():
    store = PrecedentStore(use_db=False)
    results = store.get_by_intent("w1", "follow_up", limit=1)
    assert len(results) <= 1


# --- Decision Log Retriever ---

def test_retriever_uses_query_plan():
    retriever = DecisionLogRetriever()
    plan = QueryPlan(
        intent_type="follow_up",
        raw_intent="Follow up",
        required_contexts=["precedents"],
    )
    results = retriever.retrieve("w1", plan)
    assert len(results) >= 1
    assert all(r["intent_type"] == "follow_up" for r in results)


# --- Outcome Ranker ---

def test_outcome_ranker_success_first():
    precedents = [
        {"id": "d1", "outcome": "success", "outcome_score": 0.9},
        {"id": "d2", "outcome": "failure", "outcome_score": 0.2},
    ]
    ctx, sources = rank_precedents(precedents)
    assert ctx.past_decisions[0]["id"] == "d1"  # success ranked higher
    assert len(sources) == 2


def test_outcome_ranker_empty():
    ctx, sources = rank_precedents([])
    assert len(ctx.past_decisions) == 0
    assert len(sources) == 0


def test_outcome_ranker_score_range():
    precedents = [
        {"id": "d1", "outcome": "success", "outcome_score": 0.9},
    ]
    ctx, sources = rank_precedents(precedents)
    score = ctx.past_decisions[0]["rank_score"]
    assert 0.0 <= score <= 1.0

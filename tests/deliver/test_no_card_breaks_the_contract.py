"""STEP-14 · every card the pipeline writes passes the card contract first — a decision's or a question's, new or a version.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_no_card_breaks_the_contract.py -q

Tree `yc2_w27_s14` M43.C4.L-integration.V1.U02 (`deliver/pipeline`; STEP-14 §3.5, §8.4 item 6). Before a card is
inserted or a file's card versioned, its words pass `contracts/card_contract` against what they were made from: the
facts, the quotes it may show, the tenant's own names. Refused, it is not written — counted `refused_contract:<rule>`,
logged — and a refused VERSION leaves the file's card as it was. The production cases: *"nsrcel — a dated payment
obligation is open"* (a corpus template's money claim with no money in the evidence), *"Which is right? Maria
Exconde: party.role"*, a card whose subject is us. An expert card's words were held to its dossier by its check, so its
own checked words are its corpus; the rules that reach it here are us and an internal field name.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from tests.deliver.test_an_expert_card_speaks_its_review import CORPUS_TEMPLATE, EXPERT_TEMPLATE
from tests.reason.expert.test_a_covered_file_decides_once import admitted, world  # noqa: F401 — fixtures

EVAL = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)


def _pass(monkeypatch, signals, *, templates, facts=None, quotes=(), subject="Kestrel Capital"):
    built: list = []
    monkeypatch.setattr(pipeline, "ensure_default", lambda *_a: None)
    monkeypatch.setattr(pipeline, "_open_signals_without_cards", lambda *_a: signals)
    monkeypatch.setattr(pipeline, "_open_situations_without_cards", lambda *_a: [])
    monkeypatch.setattr(pipeline, "_activated_features", lambda *_a: frozenset())
    monkeypatch.setattr(pipeline, "_cohort_absorbed", lambda *_a: set())
    monkeypatch.setattr(pipeline, "_tenant_identities", lambda *_a: ("Arjun Rao", "arjun@nimbuslabs.test"))
    monkeypatch.setattr(pipeline, "identity_for", lambda *_a: pipeline.SelfIdentity.of(
        addresses=["arjun@nimbuslabs.test"], domains=["nimbuslabs.test"]))
    monkeypatch.setattr(pipeline, "load_evidence_quotes", lambda *_a, **_k: list(quotes))
    monkeypatch.setattr(pipeline, "budget_full", lambda *_a: False)

    def _draft(_graph, _org, sig, *_a, **_k):
        return {"signal_id": sig["signal_id"], "org_id": "org_c", "_reason_code": sig["reason_code"],
                "_template": templates[sig["capability_id"]], "_facts": dict(facts or {}),
                "_slots": {"entity": subject}, "_quotes": list(quotes), "level": "prescriptive",
                "actions": [], "assignee": None, "output_lane": "decision", "business_subject": subject,
                "file_id": None}
    monkeypatch.setattr(pipeline, "build_draft", _draft)
    store = SimpleNamespace(claim_build=lambda *_a, **_k: "tok", release_build=lambda *_a: None,
                            insert_card=lambda draft, copy, **_k: built.append(copy) or (f"c{len(built)}", True, False),
                            transition=lambda *_a, **_k: False, file_card=lambda *_a: None)
    graph = SimpleNamespace(engine=None, record_cost=lambda **_k: None)
    # No narrator: the fallback template's own words reach the card, as on a pass whose model is down.
    out = pipeline.build_cards_for_org(graph=graph, card_store=store, org_id="org_c", llm=None,
                                       registry=object(), eval_time=EVAL)
    return built, out


def _signal(signal_id, capability_id, reason_code):
    return {"signal_id": signal_id, "subject_node_id": "node_k", "effective_config": {},
            "capability_id": capability_id, "reason_code": reason_code, "score": 60,
            "reasoning_run_id": "r", "reasoning_candidate_id": "c", "reasoning_decision_hash": "d" * 64,
            "config_snapshot_id": "cfg"}


MONEY = {**CORPUS_TEMPLATE, "fallback": {"headline": "Settle with {entity}",
                                         "situation": "{entity} — a dated payment obligation is open"}}


def test_a_money_claim_with_no_money_in_the_evidence_is_never_written(monkeypatch):
    built, out = _pass(monkeypatch, [_signal("s1", "expertise.money", "money_owed")],
                       templates={"expertise.money": MONEY},
                       facts={"commitment.due_at": {"value": "2026-10-09"}})
    built_money = [c for c in built if "payment" in str(c.get("situation"))]
    assert built_money == [] and out["refused_contract:money"] == 1 and out["built"] == 0, out


@pytest.mark.parametrize("facts, quotes", [
    ({"invoice.amount": {"value": "50000"}}, ()),                                   # a field that names money
    ({"commitment.text": {"value": "₹50,000 by Friday"}}, ()),                      # a currency in a value
    ({}, ({"quote": "the fee is ₹50,000", "kind": "statement"},)),                  # a currency in a quote
])
def test_with_money_in_the_evidence_the_same_card_is_written(monkeypatch, facts, quotes):
    built, out = _pass(monkeypatch, [_signal("s1", "expertise.money", "money_owed")],
                       templates={"expertise.money": MONEY},
                       facts={**facts, "commitment.due_at": {"value": "2026-10-09"}}, quotes=quotes)
    assert out["built"] == 1 and out.get("refused_contract:money", 0) == 0, out


def test_a_card_whose_subject_is_us_or_that_names_a_field_is_never_written(monkeypatch):
    _built, us = _pass(monkeypatch, [_signal("s1", "expertise.opportunity", "opportunity")],
                       templates={"expertise.opportunity": CORPUS_TEMPLATE}, subject="nimbuslabs.test")
    assert us["refused_contract:us"] == 1 and us["built"] == 0, us
    field = {**EXPERT_TEMPLATE, "fallback": {"headline": "Which is right? Maria Exconde: party.role",
                                             "situation": "a fund preparing a partner meeting"}}
    _built, expert = _pass(monkeypatch, [_signal("s2", "expert.file_review", "file_review")],
                           templates={"expert.file_review": field})
    assert expert["refused_contract:internal"] == 1 and expert["built"] == 0, expert


def test_an_expert_cards_checked_words_are_its_corpus(monkeypatch):
    """The expert's numbers and quotes were held to its dossier by its check: written, nothing refused."""
    checked = {**EXPERT_TEMPLATE, "fallback": {"headline": "Send Arjun the deck by 14 Oct",
                                               "situation": "Kavya asked “could you send the deck?” on 2 Oct, "
                                                            "before the ₹2 Cr round's invoice"}}
    built, out = _pass(monkeypatch, [_signal("s2", "expert.file_review", "file_review")],
                       templates={"expert.file_review": checked})
    assert out["built"] == 1 and not any(k.startswith("refused_contract") and v for k, v in out.items()), out


def test_every_rule_is_counted_from_zero(monkeypatch):
    _built, out = _pass(monkeypatch, [], templates={})
    from genios_engine.contracts.card_contract import RULES
    assert {f"refused_contract:{r}": 0 for r in RULES}.items() <= out.items()


@pytest.mark.pg
def test_a_refused_version_leaves_the_files_card_as_it_was(world):
    """The file's next decision says what no card may (here, an internal field's name): no version is written, the
    card's words are the ones before."""
    from tests.reason.expert.test_a_covered_file_decides_once import NOW, _compile, _fund, _write
    from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND
    pg_store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(pg_store, org)
    _write(pg_store, org, anchor, FIRST, events)
    _compile(pg_store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=pg_store, card_store=cards, org_id=org, eval_time=NOW)
    with pg_store.engine.connect() as c:
        card_id, before = c.execute(text("select card_id, headline from cards where org_id = :o"), {"o": org}).one()
    _write(pg_store, org, anchor, SECOND, events, next_move={**OTHER_MOVE, "what": "Confirm party.role with Arjun"})
    later = NOW + timedelta(hours=6)
    _compile(pg_store, org, registry, covered={anchor: SECOND}, at=later)
    out = pipeline.build_cards_for_org(graph=pg_store, card_store=cards, org_id=org, eval_time=later)
    assert out["refused_contract:internal"] == 1 and out["versioned"] == 0, out
    with pg_store.engine.connect() as c:
        headline = c.execute(text("select headline from cards where card_id = :c"), {"c": card_id}).scalar()
        versions = c.execute(text("select count(*) from card_events where card_id = :c and kind = 'card.versioned'"),
                             {"c": card_id}).scalar()
        n = c.execute(text("select count(*) from cards where org_id = :o"), {"o": org}).scalar()
    assert (headline, versions, n) == (before, 0, 1), "its words are the ones before, and no second card"
    assert _kept(pg_store, org) == [("pipeline", "internal", "party.role")]


@pytest.mark.pg
def test_a_question_that_names_a_field_is_never_carded(world):
    from tests.reason.expert.test_a_covered_file_decides_once import NOW, _compile, _fund
    from tests.reason.expert.test_a_held_file_asks import _find_out
    pg_store, org, registry, _ = world
    anchor, _situations, events = _fund(pg_store, org)
    _find_out(pg_store, org, anchor, "ffp-fund-findout-review-000", events, question="Is the party.role still open?")
    _compile(pg_store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    out = pipeline.build_cards_for_org(graph=pg_store, card_store=CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]),
                                       org_id=org, eval_time=NOW)
    assert out["refused_contract:internal"] == 1 and out["question_cards"] == 0, out
    with pg_store.engine.connect() as c:
        assert c.execute(text("select count(*) from cards where org_id = :o"), {"o": org}).scalar() == 0
    assert _kept(pg_store, org) == [("pipeline", "internal", "party.role")]


def _kept(pg_store, org):
    """STEP-14 M43.C4.L-integration.V2.U05: what the contract refused is kept where the health check reads it
    (`card_refusals`, 0222), the refused signal named."""
    with pg_store.engine.connect() as c:
        rows = c.execute(text("select r.writer, r.rule, r.found from card_refusals r join signals s "
                              "on s.org_id = r.org_id and s.signal_id = r.ref where r.org_id = :o"), {"o": org}).all()
    return [tuple(r) for r in rows]


class _Down:
    def begin(self):
        raise RuntimeError("card_refusals is not there")


def test_a_refusal_that_cannot_be_kept_still_refuses():
    from genios_engine.contracts.card_contract import Refusal
    out: dict = {}
    assert pipeline._refused(out, "org_c", {"signal_id": "s1"}, (Refusal("money", "payment"),), engine=_Down())
    assert out == {"refused_contract:money": 1, "refusals_unkept": 1}
    assert pipeline._refused(out, "org_c", {"signal_id": "s1"}, ()) is False

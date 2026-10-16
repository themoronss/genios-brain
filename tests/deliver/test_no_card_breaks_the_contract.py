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


def _pass(monkeypatch, signals, *, templates, facts=None, quotes=(), subject="Kestrel Capital", extra=None):
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
                "file_id": None, **(extra or {})}
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


#: An expert card's words that hold a date, a quote and money (s14 crosscheck, finding 4).
CHECKED = {**EXPERT_TEMPLATE, "fallback": {"headline": "Send Arjun the deck by 14 Oct",
                                           "situation": "Kavya asked “could you send the deck?” on 2 Oct, "
                                                        "before the ₹2 Cr round's invoice"}}
#: The evidence those words rest on: the quotes the check matched in the lines its move cites.
RESTS_ON = {"sources": {"headline": {"evidence": ["evt_k1"], "quotes": [
    "Hi Arjun, could you send the deck? Before 14 Oct if you can — we close the ₹2 Cr round's invoice then. Kavya"]}}}


def test_an_expert_card_is_held_to_the_evidence_it_rests_on(monkeypatch):
    """⛔ RESTATED by `yc2_w27_s14` M43.C4.L-integration.V1.U07 (the STEP-14 crosscheck, finding 4): this pinned that an
    expert card's OWN words were its corpus — so its date, its quote and its money were held by themselves, and only
    the us and internal rules could ever fire on an expert card. The check holds figures and names, not money words
    nor quoted spans. Its words are held to the evidence its move rests on (the quotes its check matched, the mail
    they are from, the file's facts) — with that evidence, written, nothing refused."""
    sig = {**_signal("s2", "expert.file_review", "file_review"), "capability_render": RESTS_ON}
    built, out = _pass(monkeypatch, [sig], templates={"expert.file_review": CHECKED})
    assert out["built"] == 1 and not any(k.startswith("refused_contract") and v for k, v in out.items()), out


def test_an_expert_cards_own_words_are_not_its_evidence(monkeypatch):
    """The same card with nothing under it: its money, its quote and its date are each refused."""
    _built, out = _pass(monkeypatch, [_signal("s2", "expert.file_review", "file_review")],
                        templates={"expert.file_review": CHECKED})
    assert out["built"] == 0, out
    assert (out["refused_contract:money"], out["refused_contract:quote"], out["refused_contract:number"]) == (1, 1, 1)


def test_what_doing_nothing_costs_is_read_too(monkeypatch):
    """`success_signal` and `do_nothing_consequence` are shown (GET /cards/{id}); the contract reads them."""
    plain = {**EXPERT_TEMPLATE, "fallback": {"headline": "Send Arjun the deck", "situation": "a fund"}}
    sig = {**_signal("s2", "expert.file_review", "file_review"), "capability_render": {"sources": {"headline": {
        "evidence": ["evt_k1"], "quotes": ["Hi Arjun, could you send the deck? Kavya"]}}}}
    built, out = _pass(monkeypatch, [sig], templates={"expert.file_review": plain},
                       extra={"do_nothing_consequence": "The party.role stays open and the late fee is charged."})
    assert out["built"] == 0 and out["refused_contract:internal"] == 1 and out["refused_contract:money"] == 1, out


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


# ── STEP-14 (fix, found re-recording 14 Oct) · the gold lines are code's, and the contract reads them as such ──
#
# Re-recording after M43.C3 (the gold shape), the contract refused 19 expert cards on the golden set — F01, F02,
# F48, F52, F63 among them: *"number: 12"* from the card's why now (*"Introly wrote on 12 Aug"*), *"quote: Ferngrove x
# Nimbus Labs"* from a meeting's title (*"the meeting “Ferngrove x Nimbus Labs” in 2 days"*). Why now and what remains
# are the lines CODE wrote from the dossier at review time (`reason/expert/card_lines`); the alternative, the stop rule
# and the move whole are the expert's words its check held (check.v3). They are an expert card's corpus, as its other
# checked words are — and they are shown, so the contract reads every one of them for us and a field's name.

def _expert_card(**over):
    # ⛔ RESTATED by `yc2_w27_s14` M43.C4.L-integration.V1.U07 (the crosscheck's finding 4): an expert card's own words
    # are no longer its corpus — its "13 Aug" is held by the evidence its move rests on, a quote its check matched.
    card = {"business_subject": "Leela Krishnan", "_facts": {}, "_slots": {}, "_quotes": [],
            "_checked_quotes": ["Leela: I sent you an invite for 13 Aug, 3 pm"],
            "why_now": "the meeting “Ferngrove x Nimbus Labs” in 2 days, on 13 Aug",
            "unresolved_item": "Leela asked for the onboarding flow, since 9 Aug",
            "recommended": {"who": "You", "what": "Accept Leela's invite for 13 Aug and read the brief", "to": None},
            "alternative": "If 13 Aug no longer works, offer Leela two other times",
            "wait_or_stop": "Wait for the call on 13 Aug; stop if Leela cancels",
            "success_signal": "the call happened", "do_nothing_consequence": "the call runs cold"}
    card.update(over)
    copy = {"headline": "Accept Leela's invite for 13 Aug", "situation": "A call with Ferngrove is booked",
            "artifact": {"body": ""}}
    return card, copy


def test_an_expert_cards_gold_lines_are_its_corpus():
    card, copy = _expert_card()
    assert pipeline._contract_refusals(card, copy, us=None, our_names=(), identities=(), expert=True) == ()


@pytest.mark.parametrize("line, said, rule", [
    ("alternative", "If party.role is wrong, ask Leela", "internal"),
    ("wait_or_stop", "Wait for {stage}", "internal"),
    ("recommended", {"who": "You", "what": "Confirm commitment.action with Leela", "to": None}, "internal"),
    ("why_now", "Leela wrote about deal.stage on 9 Aug", "internal"),
])
def test_every_gold_line_is_read_for_what_no_card_may_say(line, said, rule):
    card, copy = _expert_card(**{line: said})
    assert [r.rule for r in pipeline._contract_refusals(card, copy, us=None, our_names=(), identities=(),
                                                        expert=True)] == [rule]


def test_a_card_no_review_wrote_keeps_its_own_corpus():
    """The negative control: the narrator's card's why now is held to its facts, as before."""
    card, copy = _expert_card(recommended=None, alternative=None, wait_or_stop=None,
                              why_now="they wrote 12 days ago", unresolved_item=None)
    assert [r.rule for r in pipeline._contract_refusals(card, copy, us=None, our_names=(), identities=(),
                                                        expert=False)] == ["number"]


@pytest.mark.pg
def test_the_evidence_is_the_mail_the_move_rests_on_not_a_fragment_of_it(world):
    """`_cited_texts` reads the retained words of each mail the card's move cites (`prepared_content`) — the whole
    mail, so a date the check's quote was cut before is still held — and nothing for an id that is no mail."""
    from tests.reason.expert.test_a_covered_file_decides_once import _fund
    pg_store, org, _registry, _ = world
    _anchor, _situations, events = _fund(pg_store, org)
    ev = sorted(events)[0]
    whole = "Hi Arjun, could you send the deck? We meet on Tuesday 4 Aug at 3pm or Wednesday 5 Aug at 11am. Kavya"
    with pg_store.engine.begin() as c:
        c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
                       "values (:e, :o, :p, :t) on conflict (event_id) do update set clean_text = excluded.clean_text"),
                  {"e": ev, "o": org, "p": f"pc_{ev}", "t": whole})
    got = pipeline._cited_texts(pg_store, org, {"headline": {"evidence": [ev, "loop:l1", "num:n1"]},
                                                "situation": {"inference": "x"}})
    assert got == [whole]
    assert pipeline._cited_texts(pg_store, org, {"headline": {"evidence": ["loop:l1"]}}) == []
    assert pipeline._cited_texts(SimpleNamespace(engine=None), org, {"headline": {"evidence": [ev]}}) == []

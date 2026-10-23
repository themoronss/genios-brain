"""GeniOS-011 S34.U3 · C1, the card writer (`deliver/card_copy`): one checked model call per new card version.

`speedrun008/GeniOS-010/06-CARDS/01-INTEGRATION.md` §5 C1 and `02-CARD-DEFINITION.md` §2: the subject starts with a
verb, is about ten words, names the person or the thing, and is never a cut sentence or a placeholder; under it two
lines say what to do and how; every field is this card's own; every claim points to its source. The model writes
the words from the card's OWN facts, each sentence naming the ids it rests on; code keeps a sentence only when every
id is one the card holds and the sentence says nothing those facts do not (`deliver/claim_validator.claims_ok`).
A sentence resting on nothing is dropped, and said. No model call here is live: a fake client stands in, and the
live probe (`scripts/card_copy_probe.py`) waits on Rohit's yes to spend.

Names are the golden set's invented ones (`tests/replays/founder_case.REAL_NAMES` is the deny-list).
"""
from __future__ import annotations

import ast
import copy as _copy
import re
from pathlib import Path

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.deliver import card_copy as CC
from genios_engine.deliver.card_builder import gold_headline
from genios_engine.platform.l4_activation import FEATURE_CARD_COPY
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.bundle.budget import OWN_BUDGETS
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.gate import RSiteGate
from genios_engine.reason.expert.decide import DO_NOTHING_WITHHELD
from genios_engine.reason.llm_sites import InMemorySiteCache

ORG = "org_s34u3_writer"
_ROOT = Path(__file__).resolve().parents[2]

MOVE = "Send Tara Sethi your deck to read ahead of a call, and offer her two times for the call"
SIGNAL = {"signal_id": "sig_tara", "capability_render": {"gold": {
    "subject": "Tara Sethi", "company": "Kestrel Capital", "kind_of_work": "fundraising", "role": "investor",
    "why_now": "Tara Sethi asked for the deck before the call", "what_remains": ["send the deck"],
    "recommended": {"who": "you", "what": MOVE, "for_whom": "Tara Sethi", "by_when": "2026-10-24",
                    "to": "Tara Sethi"},
    "alternative": "Ask Tara Sethi which day suits her", "wait_or_stop": None,
    "window": {"days": 3, "said": "the file's own window", "from": "review"}}}}
CARD = {"signal_id": "sig_tara", "file_id": "node_tara", "business_subject": "Tara Sethi",
        "relationship_role": "investor", "why_now": "Tara Sethi asked for the deck before the call",
        "unresolved_item": "send the deck", "success_signal": "Tara has your deck and a call is booked",
        "do_nothing_consequence": DO_NOTHING_WITHHELD, "outcome_window_days": 3,
        "_quotes": [{"quote": "could you send me your deck before we speak?", "event_id": "evt_tara",
                     "name": "Tara Sethi", "author": "tara@kestrel.example", "source_verified": True,
                     "kind": "ask"}],
        "_facts": {"party.name": {"value": "Tara Sethi"}}}
COPY = {"headline": "Send Tara Sethi your deck to read ahead of a call",
        "situation": "An investor your connector introduced has asked for your deck"}
GOALS = ({"line_id": "cbl_seed", "text": "Close the seed round by December"},)


def ideal() -> dict:
    return _copy.deepcopy({
        "subject": {"text": "Send Tara Sethi your deck before the call", "rests_on": ["line:move", "quote:1"]},
        "summary": {"text": "Tara Sethi asked for your deck. Send it and offer her two times for the call.",
                    "rests_on": ["quote:1", "line:move"]},
        "how": {"text": "Reply to her on the thread with the deck", "rests_on": ["quote:1"]},
        "steps": [{"text": "Send Tara Sethi the deck", "rests_on": ["quote:1"]},
                  {"text": "Offer her two times for the call", "rests_on": ["line:move"]}],
        "result": {"text": "Tara has your deck and a call is booked", "rests_on": ["card:success_signal"]},
        "avoid": None,
        "done_when": {"text": "Tara has your deck and a call is booked", "rests_on": ["card:success_signal"]},
        "if_not": None,
        "alternative": {"text": "Ask Tara Sethi which day suits her", "rests_on": ["line:alternative"]},
        "goal": {"line_id": "cbl_seed", "how": "advances", "why": "a call with an investor moves the seed round",
                 "rests_on": ["cbl_seed", "card:relationship_role"]}})


class Client:
    """The shared client's shape (`context/llm/client.LLMClient`): it takes thinking, so the gate sends it."""

    model = "claude-haiku-4-5"
    supports_thinking = True

    def __init__(self, *payloads, truncated=False, raises=False):
        self.payloads = list(payloads) or [ideal()]
        self.truncated = truncated
        self.raises = raises
        self.calls: list[dict] = []

    def call(self, prompt, *, max_tokens, **kw):
        self.calls.append({"prompt": prompt, "max_tokens": max_tokens, **kw})
        if self.raises:
            raise RuntimeError("the API is down")
        payload = self.payloads[min(len(self.calls), len(self.payloads)) - 1]
        return LLMResult(parsed=payload, raw="{}", ok=True, model=self.model, input_tokens=2000,
                         output_tokens=500, truncated=self.truncated)


class Cards:
    """A card store's one method the writer uses."""

    def __init__(self):
        self.writes: list[dict] = []

    def set_copy(self, org_id, card_id, copy, *, version, headline):
        self.writes.append({"org_id": org_id, "card_id": card_id, "copy": copy, "version": version,
                            "headline": headline})
        return True


def writer(client=None, *, activated=frozenset({FEATURE_CARD_COPY}), budget=None, cache=None, goals=GOALS):
    gate = RSiteGate(org_id=ORG, engine=None, client=client if client is not None else Client(),
                     activated=activated,
                     budget=budget or NarrativeBudget.for_site(S.SITE_CARD_COPY, org_id=ORG, engine=None))
    return CC.CopyWriter(org_id=ORG, gate=gate, cache=cache if cache is not None else InMemorySiteCache(),
                         identities=("rohit@ourco.example",), goals=goals)


def write(w, cards=None, *, card=CARD, copy=COPY, signal=SIGNAL, version=1):
    return w.write(cards if cards is not None else Cards(), card_id="card_tara", version=version, card=card,
                   copy=copy, signal=signal)


# ── what the card holds, with an id each ─────────────────────────────────────────────────────

def test_the_facts_are_the_cards_own_each_with_an_id():
    facts = {f.id: f for f in CC.card_facts(CARD, COPY, SIGNAL, goals=GOALS)}
    assert facts["line:move"].text == MOVE
    assert facts["quote:1"].kind == "quote" and facts["quote:1"].source["event_id"] == "evt_tara"
    assert facts["card:success_signal"].text == "Tara has your deck and a call is booked"
    assert facts["cbl_seed"].kind == "goal"
    # A stock sentence is no fact of this card: the withheld do-nothing line is left out, never rested on.
    assert "card:do_nothing_consequence" not in facts
    assert all(len(f.text) <= CC.FACT_CHARS for f in facts.values())


# ── one checked call: what stands, and what is dropped ───────────────────────────────────────

def test_an_answer_that_rests_on_the_card_is_kept_with_what_each_sentence_rests_on():
    cards = Cards()
    stored = write(writer(), cards)
    assert stored is not None, "the ideal answer stands"
    assert stored["subject"] == "Send Tara Sethi your deck before the call"
    assert stored["summary"].startswith("Tara Sethi asked for your deck")
    assert stored["steps"] == ["Send Tara Sethi the deck", "Offer her two times for the call"]
    assert stored["result"] == "Tara has your deck and a call is booked"
    assert stored["goal"] == {"line_id": "cbl_seed", "how": "advances",
                              "why": "a call with an investor moves the seed round"}
    assert stored["rests_on"]["subject"] == ["line:move", "quote:1"]
    assert stored["rests_on"]["steps"] == [["quote:1"], ["line:move"]]
    assert stored["sources"]["quote:1"] == {"kind": "quote", "event_id": "evt_tara"}
    assert stored["avoid"] is None and stored["if_not"] is None and stored["dropped"] == {}
    assert stored["card_version"] == 1 and stored["copy_version"] == CC.COPY_VERSION
    [w] = cards.writes
    assert (w["card_id"], w["version"], w["headline"]) == ("card_tara", 1, COPY["headline"]), \
        "written for the version and the words it was made from"


@pytest.mark.parametrize("rests_on", [[], None, "quote:1", [""]])
def test_a_sentence_resting_on_nothing_is_dropped_and_said(rests_on):
    answer = ideal()
    answer["result"] = {"text": "Tara has your deck and a call is booked", "rests_on": rests_on}
    stored = write(writer(Client(answer)))
    assert stored["result"] is None and stored["dropped"]["result"] == "rests_on_nothing"
    assert stored["subject"], "its siblings stand"


def test_a_sentence_resting_on_an_id_the_card_does_not_hold_is_dropped():
    answer = ideal()
    answer["how"] = {"text": "Reply to her on the thread with the deck", "rests_on": ["quote:1", "quote:9"]}
    stored = write(writer(Client(answer)))
    assert stored["how"] is None and stored["dropped"]["how"] == "rests_on_unknown:quote:9"


@pytest.mark.parametrize("field, text, why", [
    ("summary", "Tara Sethi and Priya Kapoor asked for your deck.", "claim:name:Priya"),
    ("result", "Tara invests 5 crore after the call", "claim:number:5"),
])
def test_a_sentence_saying_what_its_own_facts_do_not_is_dropped(field, text, why):
    """Held to the facts it NAMES, not to the whole card: a sentence must cite what it says."""
    answer = ideal()
    answer[field] = {"text": text, "rests_on": ["quote:1", "line:move"]}
    stored = write(writer(Client(answer)))
    assert stored[field] is None and stored["dropped"][field] == why


def test_a_name_on_the_card_but_not_in_the_facts_cited_is_dropped():
    answer = ideal()
    answer["how"] = {"text": "Reply to Kestrel Capital about the day", "rests_on": ["line:alternative"]}
    stored = write(writer(Client(answer)))
    assert stored["how"] is None and stored["dropped"]["how"].startswith("claim:name:Kestrel")


@pytest.mark.parametrize("subject, why", [
    ("Send calendar invites with the meeting link to", "cut_sentence"),
    ("Deliver {action} to Tara Sethi today", "placeholder"),
    ("Send Tara Sethi the deck…", "placeholder"),
    ("Send Tara Sethi your deck and offer her two times for the call today", "over_ten_words"),
    ("Send Tara Sethi your deck to read well ahead of a call she asked for", "over_ten_words"),
])
def test_a_subject_that_is_cut_a_placeholder_or_long_is_dropped(subject, why):
    answer = ideal()
    answer["subject"] = {"text": subject, "rests_on": ["line:move", "quote:1"]}
    stored = write(writer(Client(answer)))
    assert stored["subject"] is None and stored["dropped"]["subject"] == why


def test_a_step_that_rests_on_nothing_is_dropped_and_its_siblings_stand():
    answer = ideal()
    answer["steps"] = [{"text": "Send Tara Sethi the deck", "rests_on": ["quote:1"]},
                       {"text": "Book the call", "rests_on": []},
                       {"text": "Offer her two times for the call", "rests_on": ["line:move"]}]
    stored = write(writer(Client(answer)))
    assert stored["steps"] == ["Send Tara Sethi the deck", "Offer her two times for the call"]
    assert stored["rests_on"]["steps"] == [["quote:1"], ["line:move"]]
    assert stored["dropped"]["steps"] == {"2": "rests_on_nothing"}


def test_more_than_four_steps_keep_the_first_four():
    answer = ideal()
    answer["steps"] = [{"text": "Send Tara Sethi the deck", "rests_on": ["quote:1"]}] * 6
    stored = write(writer(Client(answer)))
    assert len(stored["steps"]) == CC.MAX_STEPS and stored["dropped"]["steps"] == {"5": "over_four", "6": "over_four"}


@pytest.mark.parametrize("goal, why", [
    ({"line_id": "cbl_other", "how": "advances", "why": "it helps", "rests_on": ["cbl_other"]}, "not_an_accepted_goal"),
    ({"line_id": "cbl_seed", "how": "helps", "why": "it helps the seed round", "rests_on": ["cbl_seed"]}, "how_unknown"),
    ({"line_id": "cbl_seed", "how": "advances", "why": "it moves the round", "rests_on": ["card:role"]},
     "rests_on_unknown:card:role"),
    ({"line_id": "cbl_seed", "how": "advances", "why": "a call moves the seed round",
      "rests_on": ["card:relationship_role"]}, "does_not_rest_on_its_goal"),
])
def test_the_goal_is_one_the_brief_accepted_and_rests_on_it(goal, why):
    answer = ideal()
    answer["goal"] = goal
    stored = write(writer(Client(answer)))
    assert stored["goal"] is None and stored["dropped"]["goal"] == why


def test_no_accepted_goal_means_no_goal():
    stored = write(writer(goals=()))
    assert stored["goal"] is None and stored["dropped"]["goal"] == "not_an_accepted_goal"


# ── fail closed: no copy means today's fields ────────────────────────────────────────────────

def test_an_answer_where_nothing_stands_writes_no_copy():
    answer = {field: {"text": "Ring Priya Kapoor", "rests_on": ["quote:1"]} for field in CC.SENTENCE_FIELDS}
    answer.update(steps=[], goal=None)
    cards, client = Cards(), Client(answer)
    w = writer(client)
    assert write(w, cards) is None and cards.writes == []
    assert w.last_receipt.outcome == S.OUTCOME_FAILED_VALIDATION
    assert len(client.calls) == 1, "a refusal on substance is not argued with"


def test_a_shape_not_asked_for_is_asked_for_once_more():
    misshapen = ideal()
    misshapen["subject"] = "Send Tara Sethi your deck"           # a string, not {"text", "rests_on"}
    client = Client(misshapen, ideal())
    stored = write(writer(client))
    assert stored is not None and len(client.calls) == 2
    assert "not in the shape asked for" in client.calls[1]["prompt"]


@pytest.mark.parametrize("client, outcome", [
    (None, S.OUTCOME_NO_CLIENT),
    (Client(truncated=True), S.OUTCOME_TRUNCATED),
    (Client(raises=True), S.OUTCOME_FAILED_GENERATION),
])
def test_no_model_a_cut_answer_or_a_raise_writes_no_copy_and_never_raises(client, outcome):
    gate = RSiteGate(org_id=ORG, engine=None, client=client, activated=frozenset({FEATURE_CARD_COPY}),
                     budget=NarrativeBudget.for_site(S.SITE_CARD_COPY, org_id=ORG, engine=None))
    w = CC.CopyWriter(org_id=ORG, gate=gate, cache=InMemorySiteCache(), goals=GOALS)
    cards = Cards()
    assert write(w, cards) is None and cards.writes == []
    assert w.last_receipt.outcome == outcome


def test_a_card_with_no_facts_spends_nothing():
    client = Client()
    w = writer(client)
    assert w.write(Cards(), card_id="c", version=1, card={"signal_id": "s"}, copy={}, signal={}) is None
    assert client.calls == [] and w.last_receipt.outcome == S.OUTCOME_NO_PRECONDITION


def test_a_store_that_raises_costs_the_copy_never_the_card():
    class Broken(Cards):
        def set_copy(self, *a, **k):
            raise RuntimeError("database gone")
    assert write(writer(), Broken()) is None


# ── its own site, its own budget, one call per version and never per view ───────────────────

def test_the_site_is_its_own_with_its_own_day_tier_ceiling_and_no_thinking():
    assert S.SITE_CARD_COPY == "R-10" and S.SITE_CARD_COPY in S.R_SITES
    assert S.tier_for(S.SITE_CARD_COPY) == S.TIER_T1
    assert S.max_output_tokens(S.SITE_CARD_COPY) == 1600
    assert S.thinking_mode(S.SITE_CARD_COPY) == "off" and S.timeout_s(S.SITE_CARD_COPY) is None
    assert OWN_BUDGETS[S.SITE_CARD_COPY] == ("0.50", "0.02")
    client = Client()
    write(writer(client))
    [call] = client.calls
    assert call["max_tokens"] == 1600 and call["thinking"] == "off"


def test_the_worst_case_prompt_fits_the_per_call_ceiling():
    """The fact table at its bound priced at the ceiling stays under two cents — a busy card is not refused."""
    from genios_engine.reason.bundle.budget import estimate_micro_usd, usd_to_micro
    facts = tuple(CC.Fact(f"fact:{i}", "fact", "x" * CC.FACT_CHARS, {}) for i in range(CC.MAX_FACTS))
    prompt = CC.build_prompt(facts)
    assert estimate_micro_usd(site=S.SITE_CARD_COPY, prompt_chars=len(prompt), max_output_tokens=1600) \
        <= usd_to_micro(OWN_BUDGETS[S.SITE_CARD_COPY][1])


def test_a_spent_day_writes_no_copy_and_calls_nothing():
    client = Client()
    w = writer(client, budget=NarrativeBudget(org_id=ORG, site=S.SITE_CARD_COPY, daily_cap_micro_usd=1,
                                              per_call_cap_micro_usd=20_000))
    assert write(w) is None and client.calls == []
    assert w.last_receipt.outcome == S.OUTCOME_NO_BUDGET


def test_the_switch_off_builds_no_writer_and_reads_nothing():
    class Graph:
        @property
        def engine(self):
            raise AssertionError("an unarmed tenant reads nothing")
    assert CC.CopyWriter.for_pass(graph=Graph(), org_id=ORG, activated=frozenset(), eval_time=None) is None


def test_one_call_per_new_version_and_the_same_facts_again_cost_nothing():
    client, cache = Client(), InMemorySiteCache()
    w = writer(client, cache=cache)
    first, again = write(w, version=1), write(w, version=2)
    assert len(client.calls) == 1, "a version whose facts did not move is answered from the record"
    assert again["subject"] == first["subject"] and again["card_version"] == 2
    moved = {**CARD, "success_signal": "Tara has your deck and the call is on Thursday"}
    write(w, card=moved, version=3)
    assert len(client.calls) == 2, "new facts, one new call"


def test_only_the_card_pass_calls_the_writer_never_a_read():
    """Never per view: the only engine module that imports the writer is the pass that builds and versions cards."""
    importers = []
    for path in sorted((_ROOT / "genios_engine").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "genios_engine.deliver.card_copy":
                importers.append(str(path.relative_to(_ROOT)))
            elif isinstance(node, ast.ImportFrom) and node.level and node.module == "card_copy":
                importers.append(str(path.relative_to(_ROOT)))
    assert sorted(set(importers)) == ["genios_engine/deliver/pipeline.py"], importers


def test_the_prompt_names_every_fact_by_its_id_and_asks_for_rests_on():
    client = Client()
    write(writer(client))
    prompt = client.calls[0]["prompt"]
    assert "[line:move]" in prompt and "[quote:1]" in prompt and "[cbl_seed]" in prompt
    assert '"rests_on"' in prompt and "thrown away" in prompt
    assert "rohit@ourco.example" not in prompt, "the tenant's own addresses ground; they are not facts"


# ── golden headline assertions: the writer's subject beside the code's own cut ─────────────

GOLDEN = [
    # (the move as the expert held it, the card's quote, the subject the writer is asked for, the code's cut)
    ("Reply to Sofia Brandt accepting a twenty-minute product demo and proposing Tuesday or Wednesday afternoon",
     "could we do a twenty-minute product demo next week?",
     "Accept Sofia Brandt's product demo and propose Tuesday",
     "Reply to Sofia Brandt accepting a twenty-minute product demo"),
    ("Ask Kavitha Nair at Lakshya Accelerator whether the Demo Day slot on the twentieth is still held for us",
     "is the Demo Day slot on the twentieth still yours?",
     "Ask Kavitha Nair if the Demo Day slot is held",
     "Ask Kavitha Nair at Lakshya Accelerator"),
    ("Accept the invite from Leela Krishnan of Ferngrove and read a one-page brief on her company before the "
     "call on Thursday", "would you join a call on Thursday?",
     "Accept Leela Krishnan's Thursday call and read her brief",
     "Accept the invite from Leela Krishnan of Ferngrove"),
]


@pytest.mark.parametrize("move, quote, subject, cut", GOLDEN)
def test_golden_headlines(move, quote, subject, cut):
    """The code's cut (the fail-closed headline, `card_builder.gold_headline`) is pinned beside the subject the
    writer is asked for: verb first, at most ten words, names the person — and held to the card's own facts."""
    assert gold_headline(move) == cut
    signal = _copy.deepcopy(SIGNAL)
    signal["capability_render"]["gold"]["recommended"]["what"] = move
    card = {**CARD, "_quotes": [{**CARD["_quotes"][0], "quote": quote}]}
    answer = ideal()
    answer["subject"] = {"text": subject, "rests_on": ["line:move", "quote:1"]}
    stored = write(writer(Client(answer)), card=card, signal=signal)
    assert stored["subject"] == subject and "subject" not in stored["dropped"]
    assert len(subject.split()) <= CC.SUBJECT_MAX_WORDS and len(subject) <= CC.CAPS["subject"]


def test_the_queue_serves_the_copy_through_all_three_doors():
    """The copy's subject and two lines reach every queue door — the decision's, the P4 situation's and the
    question's — spelled once in `QUEUE_COPY_SQL` and in place in each (so the census reads each door whole)."""
    import inspect

    from genios_engine.deliver import store
    source = inspect.getsource(store.CardStore.queue)
    spelled = " ".join(store.QUEUE_COPY_SQL.split())
    flat = " ".join(re.sub(r'"\s*\n\s*"', "", source).split())
    assert flat.count(spelled) == 3, "every door serves the copy"

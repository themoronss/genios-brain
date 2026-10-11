"""STEP-12 · the checklist prompt — the thinking a 30-year chief of staff does, in order, over one file's dossier.

    pytest tests/reason/expert/test_the_checklist_prompt.py -q

`reason/expert/prompt.py` (tree `yc2_w27_s12` M32.C3.L-logic.V0.U01; STEP-12 §3.2, `05` §4). The
checklist's steps are the prompt's sections in their one order — what is true; the frame and its rivals;
expected against actual; patterns and counter-patterns; what is not known; the scenarios; the appraisal;
the mode; the next move; the draft — and together they ask for exactly the fields the review contract
reads, each once, in the contract's own shape and vocabularies. The dossier rides whole, first. No number
appears that the dossier does not hold: the instructions carry no digit at all. A repair carries the
gate's complaint. `PROMPT_VERSION` is "expert-review.v2": ⛔ moved from v1 by M32.C1.L-contract.V0.U09, when the frame step
began to ask for a proposed kind of work (no review was ever written under v1).
"""
from __future__ import annotations

import json

import pytest

from genios_engine.contracts.company_brief import WORK_KINDS
from genios_engine.contracts.expert_review import (LEVELS, MODES, PATTERN_KINDS, REFUSALS,
                                                   REVERSIBILITY, ExpertReview, number_tokens)
from genios_engine.reason.bundle.budget import OWN_BUDGETS, estimate_micro_usd, usd_to_micro
from genios_engine.reason.bundle.sites import SITE_EXPERT, max_output_tokens
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import prompt as P
from tests.reason.expert.test_the_dossier import _parts, _playbook

pytestmark = pytest.mark.unit

ORDER = ("true", "frame", "expected", "patterns", "unknowns", "scenarios", "appraisal", "mode",
         "next_move", "draft")

#: A review with every list holding an object, so its shape is the contract's whole shape.
FULL = {
    "facts": [{"claim": "Kunal sent the link again", "evidence": ["evt_003"]}],
    "inferences": [{"claim": "the next move is ours", "based_on": ["fact:1"]}],
    "patterns": [{"kind": "pattern", "claim": "a first call that books itself rarely ghosts",
                  "based_on": ["founder_office.heu.investor.claim_0"]}],
    "hypotheses": [{"proposition": "the fund is keen", "needs": "a partner asking for a deck"}],
    "unknowns": [{"question": "who leads at the fund", "relevance": "it decides whom to write"}],
    "frames": {"primary": "a first call being booked", "rivals": ["a polite brush-off"]},
    "expected_vs_actual": {"stage": "first_call", "expected": "the call booked",
                           "actual": "we have not booked it"},
    "scenarios": {"do_nothing": "the fund moves on", "act": "the call happens",
                  "best": "a partner meeting", "worst": "a pass", "signals_to_watch": ["an invite"]},
    "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                  "reasons": ["our move"]},
    "mode": "act", "next_move": {"who": "the founder", "what": "book the call", "for_whom": "Kunal",
                                 "by_when": "2026-10-11"},
    "alternative": "ask Kunal for a slot", "wait_or_stop": "stop if the fund passes",
    "done_when": "the call is on the calendar", "draft": "Hi Kunal, booking it now.",
    "proposed_kind": {"kind": "investor", "why": "the fund asks for a first call",
                      "evidence": ["evt_003"]}}


def _dossier(**kw) -> D.Dossier:
    return D.build_dossier(_parts(**kw))


def _shape(value):
    """Keys all the way down; a list of objects as its first object's shape, any other list as []."""
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0])] if value and isinstance(value[0], dict) else []
    return None


def test_the_prompt_has_a_version():
    assert P.PROMPT_VERSION == "expert-review.v2"


def test_the_checklist_is_the_prompts_sections_in_their_one_order():
    assert tuple(step.name for step in P.CHECKLIST) == ORDER
    d = _dossier()
    prompt = P.build_prompt(d)
    at = [prompt.index(f"### {step.title}\n{step.asks}") for step in P.CHECKLIST]
    assert at == sorted(at) and len(set(at)) == len(at)
    # the dossier first, then the rules, the checklist, the answer's schema, and the last word
    marks = [prompt.index(d.text), prompt.index(P.RULES_HEADING), prompt.index(P.CHECKLIST_HEADING),
             at[0], at[-1], prompt.index(P.SCHEMA_HEADING), prompt.index(P.LAST_WORD)]
    assert marks == sorted(marks), marks
    assert prompt.endswith(P.LAST_WORD)


def test_together_the_steps_ask_for_every_field_of_the_review_once():
    asked = [field for step in P.CHECKLIST for field in step.fields]
    assert len(asked) == len(set(asked)), asked
    assert set(asked) == set(ExpertReview.from_mapping(FULL).as_mapping()) == set(P.SCHEMA)


def test_the_schema_is_the_contracts_own_shape_and_rides_as_json():
    assert _shape(P.SCHEMA) == _shape(ExpertReview.from_mapping(FULL).as_mapping())
    prompt = P.build_prompt(_dossier())
    assert P.schema_text() in prompt and json.loads(P.schema_text()) == P.SCHEMA


def test_the_contracts_vocabularies_are_the_prompts():
    assert tuple(P.MODE_MEANINGS) == MODES
    assert P.SCHEMA["mode"] == " | ".join(MODES)
    assert P.SCHEMA["appraisal"]["stakes"] == P.SCHEMA["appraisal"]["urgency"] == " | ".join(LEVELS)
    assert P.SCHEMA["appraisal"]["reversibility"] == " | ".join(REVERSIBILITY)
    assert P.SCHEMA["patterns"][0]["kind"] == " | ".join(PATTERN_KINDS)
    assert P.SCHEMA["proposed_kind"]["kind"] == " | ".join(WORK_KINDS)
    frame = next(step for step in P.CHECKLIST if step.name == "frame")
    assert "proposed_kind" in frame.fields and "never applied" in frame.asks
    prompt = P.build_prompt(_dossier())
    mode_step = next(step for step in P.CHECKLIST if step.name == "mode")
    for mode, meaning in P.MODE_MEANINGS.items():
        assert f"{mode} — {meaning}" in mode_step.asks
    assert "act or find_out always name a next move" in prompt


def test_every_refusal_the_validator_makes_has_its_rule_in_the_prompt():
    assert set(P.RULE_FOR_REFUSAL) == set(REFUSALS)
    prompt = P.build_prompt(_dossier())
    for refusal, rule in P.RULE_FOR_REFUSAL.items():
        assert rule in P.RULES and f"- {rule}" in prompt, refusal
    assert prompt.index(P.RULES_HEADING) < prompt.index(f"- {P.RULES[0]}")


def test_the_dossier_rides_whole_and_the_same_dossier_is_the_same_prompt():
    d = _dossier()
    prompt = P.build_prompt(d)
    assert prompt.count(d.text) == 1
    assert P.build_prompt(_dossier()) == prompt                            # byte for byte
    other = _dossier(playbook=_playbook(reviewed=True))
    assert P.build_prompt(other) != prompt and other.text in P.build_prompt(other)


def test_the_instructions_hold_no_number_at_all():
    """`validate` refuses a number its dossier does not hold — so the prompt writes none of its own."""
    d = _dossier()
    prompt = P.build_prompt(d)
    assert number_tokens(prompt.replace(d.text, "")) == frozenset()
    for step in P.CHECKLIST:
        assert number_tokens(f"{step.title} {step.asks}") == frozenset(), step.name
    assert number_tokens(" ".join(P.RULES)) == frozenset()


def test_every_number_in_the_prompt_is_the_dossiers():
    d = _dossier()
    stated = number_tokens(P.build_prompt(d))
    assert stated and stated <= d.catalogue.numbers, sorted(stated - d.catalogue.numbers)


def test_a_repair_carries_the_gates_complaint_before_the_last_word():
    d = _dossier()
    plain = P.build_prompt(d)
    complaint = "Your previous answer was not valid JSON. Answer with the JSON object only."
    repaired = P.build_prompt(d, feedback=complaint)
    assert P.REPAIR_HEADING not in plain and complaint not in plain
    assert repaired.index(P.SCHEMA_HEADING) < repaired.index(P.REPAIR_HEADING) \
        < repaired.index(complaint) < repaired.index(P.LAST_WORD)
    assert repaired.endswith(P.LAST_WORD)
    assert P.build_prompt(d, feedback="  ") == plain                        # no complaint, no section


def test_a_maximal_prompt_is_affordable_under_the_experts_own_per_call_ceiling():
    """The dossier is bounded at `DOSSIER_CHARS`; the instructions add their own length, once."""
    d = _dossier()
    instructions = len(P.build_prompt(d)) - len(d.text)
    cost = estimate_micro_usd(site=SITE_EXPERT, prompt_chars=D.DOSSIER_CHARS + instructions,
                              max_output_tokens=max_output_tokens(SITE_EXPERT))
    assert cost <= usd_to_micro(OWN_BUDGETS[SITE_EXPERT][1]), cost

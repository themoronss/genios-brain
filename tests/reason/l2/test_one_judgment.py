"""GeniOS-008 L2 · one judgment of one subject: the prompt, the call through R-9's gate, the check, the result,
its needs, its replay — hermetic (a scripted client, `engine=None`).

    pytest tests/reason/l2/test_one_judgment.py -q
"""
from __future__ import annotations

import re

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.reasoning_result import (ENDED_FAILED, ENDED_OVER_BUDGET, ENDED_REFUSED,
                                                      ENDED_RESULT, LANE_DECISION, LANE_INVESTIGATION,
                                                      ReasoningResult)
from genios_engine.platform.self_identity import SelfIdentity
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import prompt as EP
from genios_engine.reason.l2 import evidence as EV
from genios_engine.reason.l2 import prompt as P
from genios_engine.reason.l2 import store as ST
from genios_engine.reason.l2.judge import judge
from genios_engine.reason.l2.replay import replay_row
from tests.reason.expert.test_the_dossier import NOW
from tests.reason.l2.world import ORG, answer, file_world

pytestmark = pytest.mark.unit

PARTS, SUBJECT, TOOLS, PLAN, DOSSIER = file_world()
PEOPLE = D.people_of(PARTS, us=SelfIdentity(), our_names=())


def _answer(payload=None, *, ok=True, truncated=False) -> LLMResult:
    return LLMResult(parsed=payload or {}, raw="{}", ok=ok, model="claude-sonnet-5", input_tokens=20000,
                     output_tokens=3000, truncated=truncated, error=None if ok else "unparseable JSON")


class _Client:
    model = "claude-sonnet-5"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400, **_):
        self.prompts.append(prompt)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def _gate(client, *, activated=frozenset({"l2_reasoning"}), spent=0):
    budget = NarrativeBudget.for_site(S.SITE_REASON, org_id=ORG)
    budget.charge(spent)
    return G.RSiteGate(org_id=ORG, engine=None, client=client, store=None, activated=activated, budget=budget)


def _judge(client, plan=PLAN, **gate):
    return judge(org_id=ORG, request_ref="l2req:t", dossier=DOSSIER, plan=plan, gate=_gate(client, **gate),
                 fingerprint="l2fp:t", context_ref="graph@41", expertise_ref="pkg:t", at=NOW, people=PEOPLE)


# ── the prompt ─────────────────────────────────────────────────────────────────────────────────

def test_the_prompt_carries_the_whole_dossier_the_experts_rules_and_both_halves_of_the_schema():
    prompt = P.build_prompt(DOSSIER, PLAN)
    assert DOSSIER.text in prompt
    for rule in EP.RULES[1:]:
        assert rule in prompt                       # the expert's rules, reused whole
    for key in ("facts", "next_move", "confidence", "options", "proposed_mutations", "evidence_needs"):
        assert f'"{key}"' in prompt


def test_the_prompt_writes_no_number_of_its_own():
    """`reason/expert/prompt`'s rule: every number the model reads is the dossier's."""
    prompt = P.build_prompt(DOSSIER, PLAN).replace(DOSSIER.text, "")
    assert re.findall(r"\d", prompt.replace("YYYY-MM-DD", "")) == []


def test_the_lane_is_never_asked_of_the_model():
    assert '"lane"' not in P.schema_text()


# ── the judgment ───────────────────────────────────────────────────────────────────────────────

def test_a_good_answer_is_a_checked_result_with_its_lane():
    client = _Client(_answer(answer()))
    judged = _judge(client)
    assert judged.ended == ENDED_RESULT, judged.reason
    r = judged.result
    assert isinstance(r, ReasoningResult) and r.lane == LANE_DECISION
    assert r.frame == "a first call being booked" and r.context_ref == "graph@41"
    assert r.check_fate in ("shown", "held")
    assert len(client.prompts) == 1


def test_a_finding_out_answer_routes_to_investigation():
    raw = answer(mode="find_out", intervention_mode="gather_evidence")
    judged = _judge(_Client(_answer(raw)))
    assert judged.ended == ENDED_RESULT and judged.result.lane == LANE_INVESTIGATION


def test_an_answer_that_contradicts_itself_is_refused_on_substance():
    judged = _judge(_Client(_answer(answer(intervention_mode="abstain"))))
    assert judged.ended == ENDED_REFUSED and "mode_mismatch" in judged.reason


def test_a_misshapen_answer_is_repaired_once_then_fails():
    raw = answer()
    del raw["confidence"]["causal"]
    client = _Client(_answer(raw))
    judged = _judge(client)
    assert judged.ended == ENDED_FAILED and len(client.prompts) == 2
    assert "causal" in client.prompts[1]                 # the repair names what was missing


def test_a_misshapen_answer_repaired_is_a_result():
    bad = answer()
    del bad["confidence"]["causal"]
    client = _Client(_answer(bad), _answer(answer()))
    assert _judge(client).ended == ENDED_RESULT and len(client.prompts) == 2


def test_an_answer_citing_nothing_the_dossier_printed_is_refused():
    raw = answer()
    raw["facts"] = [{"claim": "Kunal said yes", "evidence": ["evt_999"]}]
    judged = _judge(_Client(_answer(raw)))
    assert judged.ended in (ENDED_REFUSED, ENDED_FAILED)
    assert judged.result is None


def test_an_unprinted_case_is_dropped_and_the_result_stands():
    raw = answer(history_used=[{"case": "a fund", "applies": True, "why": "same", "based_on": ["case:nope"]}])
    judged = _judge(_Client(_answer(raw)))
    assert judged.ended == ENDED_RESULT and judged.result.history_used == ()
    assert any(k == "unprinted_ref" for k, _ in judged.result.problems)


def test_no_budget_is_carried_with_no_call():
    client = _Client(_answer(answer()))
    judged = _judge(client, spent=2_000_000)
    assert judged.ended == ENDED_OVER_BUDGET and client.prompts == []


def test_switched_off_reaches_no_question_and_spends_nothing():
    client = _Client(_answer(answer()))
    judged = _judge(client, activated=frozenset())
    assert judged.ended is None and client.prompts == []


def test_the_judgment_never_runs_on_the_experts_switch():
    client = _Client(_answer(answer()))
    assert _judge(client, activated=frozenset({"expert_review"})).ended is None


# ── needs and replay ───────────────────────────────────────────────────────────────────────────

def test_a_decision_changing_unknown_becomes_one_need_with_a_stable_id():
    r = _judge(_Client(_answer(answer()))).result
    [need] = EV.needs_from(r, org_id=ORG, trace_id="tr", eval_time=NOW)
    assert need.subject_ref == "thread:th_1" and need.need_id.startswith("l2need:")
    assert need.need_id == EV.need_id_for(ORG, r.subject_ref, "Did we already send a calendar invite  from another address?")
    assert need.expires_at > NOW


def test_a_need_that_would_not_change_the_answer_is_not_asked():
    raw = answer(evidence_needs=[{"question": "what is Kunal's title?", "why_it_matters": "curiosity",
                                  "decision_changing": False}])
    r = _judge(_Client(_answer(raw))).result
    assert EV.needs_from(r, org_id=ORG, trace_id="tr", eval_time=NOW) == []


def test_a_stored_result_replays_with_no_model_and_the_same_hash():
    r = _judge(_Client(_answer(answer()))).result
    row = ST.StoredResult(subject_ref=r.subject_ref, fingerprint="l2fp:t", status=ST.RESULT, reason=None,
                          depth=r.depth, lane=r.lane, result=r.as_mapping(),
                          receipt={"output_hash": r.output_hash()},
                          dossier={"text": DOSSIER.text, "evidence_ids": sorted(DOSSIER.catalogue.evidence_ids),
                                   "numbers": sorted(DOSSIER.catalogue.numbers),
                                   "stages": list(DOSSIER.catalogue.stages)},
                          prompt_version=P.PROMPT_VERSION, reasoned_at=NOW)
    replayed = replay_row(row, PEOPLE)
    assert replayed.output_hash_matches and replayed.check_fate == r.check_fate
    assert replayed.result.as_mapping() == r.as_mapping()


def test_the_mails_words_are_evidence_never_instructions():
    assert P._UNTRUSTED in P.build_prompt(DOSSIER, PLAN)
    assert P.build_prompt(DOSSIER, PLAN).index("<dossier>") < P.build_prompt(DOSSIER, PLAN).index(P._UNTRUSTED)

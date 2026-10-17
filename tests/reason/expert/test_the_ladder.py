"""STEP-13b · the expert's ladder — Haiku asks first, repairs once with the check's verdicts, Sonnet only if that failed.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_ladder.py

Tree `yc2_w27_s13b` M38.C2.L-logic.V3.U02 (`reason/expert/ladder`, the rule is `contracts/model_ladder`). Every rung is its
own gate with its own client and so its own model, all sharing ONE day's budget; each consult is priced at its rung's
tier. An answer the check shows, suppresses or holds for the file's own state is final; one that fails for the writer's
own fault is asked once more on its rung with the verdicts, and climbs only if that fails too; a cut answer climbs
unrepaired; a day spent stops the climb and carries the file; when every rung failed the best fate stands.
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts import claim_check as C
from genios_engine.contracts import model_ladder as M
from genios_engine.platform import l4_activation as ACT
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.expert import ladder as L
from genios_engine.reason.expert import review as R
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

ORG = "org_ladder"
FAITHFUL = W.answer()
#: A fact the move rests on cites an id nobody printed: the move is held, the writer's fault.
HELD = W.answer(fact1={"evidence": ["evt_never_shown"]})
#: Every fact cites nothing: nothing stands, refused on substance.
NOTHING = W.answer(fact1={"evidence": []}, fact2={"evidence": []}, fact3={"evidence": []}, fact4={"evidence": []})


class Scripted:
    """A model that answers from a script, one entry per call; remembers every prompt it was asked."""

    def __init__(self, model, *answers, tokens=(9_000, 900)):
        self.model, self.answers, self.prompts, self.tokens = model, list(answers), [], tokens

    def call(self, prompt, *, max_tokens=400, **_kw):
        self.prompts.append(prompt)
        answer = self.answers.pop(0) if self.answers else FAITHFUL
        if answer == "cut":
            return LLMResult(parsed={}, raw="{", ok=False, model=self.model, input_tokens=self.tokens[0],
                             output_tokens=max_tokens, error=None, truncated=True)
        if answer == "junk":
            return LLMResult(parsed={}, raw="not json", ok=False, model=self.model, input_tokens=self.tokens[0],
                             output_tokens=10, error="parse")
        return LLMResult(parsed=answer, raw="{}", ok=True, model=self.model, input_tokens=self.tokens[0],
                         output_tokens=self.tokens[1])


def _rungs(*scripts, budget=None):
    """One rung per script, sharing one budget: (tier, client) pairs in climbing order."""
    budget = budget or B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG)
    tiers = (S.TIER_T1, S.TIER_T2, S.TIER_T3)[:len(scripts)]
    out = []
    for tier, client in zip(tiers, scripts):
        gate = G.RSiteGate(org_id=ORG, engine=None, client=client,
                           activated=frozenset({ACT.FEATURE_EXPERT_REVIEW}), budget=budget)
        out.append(L.Rung(tier, gate))
    return out, budget


def _climb(*scripts, world_kw=None, budget=None):
    dossier, people = W.world(**(world_kw or {}))
    rungs, budget = _rungs(*scripts, budget=budget)
    return L.run_ladder(org_id=ORG, dossier=dossier, fingerprint="ffp-1", people=people, rungs=rungs, check=R.check), budget


def _haiku(*a, **k):
    return Scripted("claude-haiku-4-5", *a, **k)


def _sonnet(*a, **k):
    return Scripted("claude-sonnet-5", *a, **k)


# ── the cheapest rung asks first, and an answer that stands is the end of it ───────────────────

def test_a_faithful_answer_on_the_first_rung_is_final_and_the_stronger_rung_is_never_asked():
    haiku, sonnet = _haiku(FAITHFUL), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    assert len(outcome.attempts) == 1 and outcome.stood is outcome.attempts[0]
    first = outcome.stood
    assert (first.rung, first.tier, first.consult, first.status, first.fate, first.climbed_because) == (
        1, "T1", "first", "valid", "shown", None)
    assert first.model == "claude-haiku-4-5" and first.review is not None and first.checked.fate == C.SHOWN
    assert len(haiku.prompts) == 1 and sonnet.prompts == []
    assert not outcome.carried


def test_the_prompt_names_no_model_and_each_rung_is_its_own_clients_model():
    haiku = _haiku(HELD, HELD)
    sonnet = _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    assert [a.model for a in outcome.attempts] == ["claude-haiku-4-5", "claude-haiku-4-5", "claude-sonnet-5"]
    assert not any("haiku" in p.lower() or "sonnet" in p.lower() for p in haiku.prompts + sonnet.prompts)


# ── a failed answer is repaired once on its own rung, with the check's verdicts ────────────────

def test_a_failed_answer_is_asked_once_more_on_its_rung_with_the_checks_verdicts():
    haiku, sonnet = _haiku(HELD, FAITHFUL), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    first, again = outcome.attempts
    assert (first.consult, first.status, first.fate, first.climbed_because) == ("first", "valid", "held", None)
    assert (again.consult, again.rung, again.fate) == ("repair", 1, "shown")
    assert outcome.stood is again and sonnet.prompts == [], "the repaired answer ended the climb"
    assert C.UNKNOWN_EVIDENCE in haiku.prompts[1] and "evt_never_shown" in haiku.prompts[1], "the verdicts were handed back"
    assert "YOUR LAST ANSWER" in haiku.prompts[1] and "YOUR LAST ANSWER" not in haiku.prompts[0]


def test_a_repaired_answer_that_still_fails_climbs_and_the_climb_is_named_on_the_attempt_that_made_it():
    haiku, sonnet = _haiku(HELD, HELD), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    assert [(a.rung, a.consult, a.climbed_because) for a in outcome.attempts] == [
        (1, "first", None), (1, "repair", "unknown_evidence"), (2, "first", None)]
    assert outcome.stood.rung == 2 and outcome.stood.fate == C.SHOWN
    assert "YOUR LAST ANSWER" not in sonnet.prompts[0], "a rung's first ask is the fresh checklist"


def test_a_malformed_answer_after_its_syntax_repair_is_repaired_once_more_then_climbs():
    haiku, sonnet = _haiku("junk", "junk", "junk", "junk"), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    assert [(a.rung, a.consult, a.status, a.climbed_because) for a in outcome.attempts] == [
        (1, "first", "failed", None), (1, "repair", "failed", "malformed"), (2, "first", "valid", None)]
    assert "not valid JSON" in haiku.prompts[1], "the gate's own syntax retry says what was wrong"
    assert "not valid JSON" in haiku.prompts[2], "the repair's complaint says what was wrong"


def test_a_cut_answer_climbs_without_a_repair_at_the_same_ceiling():
    haiku, sonnet = _haiku("cut"), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    assert [(a.rung, a.consult, a.status, a.climbed_because) for a in outcome.attempts] == [
        (1, "first", "truncated", "truncated"), (2, "first", "valid", None)]
    assert len(haiku.prompts) == 1


def test_a_review_where_nothing_stands_is_repaired_with_its_verdicts_then_climbs():
    haiku, sonnet = _haiku(NOTHING, NOTHING), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet)
    assert [(a.consult, a.status, a.fate, a.climbed_because) for a in outcome.attempts[:2]] == [
        ("first", "refused", "refused", None), ("repair", "refused", "refused", "nothing_stands")]
    assert "fact:1 (uncited)" in haiku.prompts[1]
    assert outcome.stood.rung == 2


# ── what is no writer's fault does not climb ───────────────────────────────────────────────────

def test_an_answer_held_for_the_files_own_state_is_final_whatever_a_stronger_model_would_say():
    """The deck ask is answered by our reply (`replied_at`): the move is suppressed — final on the first rung."""
    from datetime import datetime, timezone
    haiku, sonnet = _haiku(W.answer(move={"answers": W.ASK_DECK})), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet, world_kw={"replied_at": datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)})
    assert len(outcome.attempts) == 1 and outcome.stood.fate == C.SUPPRESSED and sonnet.prompts == []


# ── every rung failed: the best fate stands ────────────────────────────────────────────────────

def test_when_every_rung_failed_the_best_fate_stands_and_the_top_rung_is_not_climbed_off():
    haiku, sonnet = _haiku(HELD, HELD), _sonnet(NOTHING, NOTHING)
    outcome, _ = _climb(haiku, sonnet)
    assert len(outcome.attempts) == 4
    assert outcome.stood.fate == C.HELD and outcome.stood.rung == 1 and outcome.stood.consult == "repair", (
        "held beats refused; on a tie the repaired answer")
    assert outcome.attempts[-1].climbed_because is None, "the top rung climbs no further"
    assert outcome.stood.review is not None and outcome.stood.status == "valid"


def test_a_single_rung_ladder_repairs_once_and_stands():
    outcome, _ = _climb(_sonnet(HELD, HELD))
    assert [a.consult for a in outcome.attempts] == ["first", "repair"] and outcome.stood.fate == C.HELD


def test_with_no_check_among_them_the_last_consult_stands():
    outcome, _ = _climb(_haiku("junk", "junk", "junk", "junk"), _sonnet("junk", "junk", "junk", "junk"))
    assert outcome.stood is outcome.attempts[-1] and outcome.stood.status == "failed"


# ── one day for every rung ─────────────────────────────────────────────────────────────────────

def test_every_consult_draws_on_the_same_day_at_its_own_rungs_price():
    haiku, sonnet = _haiku(HELD, HELD), _sonnet(FAITHFUL)
    outcome, budget = _climb(haiku, sonnet)
    h = B.cost_micro_usd(tier="T1", input_tokens=9_000, output_tokens=900)
    s = B.cost_micro_usd(tier="T2", input_tokens=9_000, output_tokens=900)
    assert [a.cost_micro_usd for a in outcome.attempts] == [h, h, s]
    assert budget.spent_micro_usd == 2 * h + s == outcome.cost_micro_usd
    assert outcome.input_tokens == 27_000 and outcome.output_tokens == 2_700


def test_a_day_spent_mid_climb_stops_it_and_carries_the_file():
    budget = B.NarrativeBudget(org_id=ORG, site=S.SITE_EXPERT, daily_cap_micro_usd=60_000, per_call_cap_micro_usd=100_000)
    haiku, sonnet = _haiku(HELD, HELD), _sonnet(FAITHFUL)
    outcome, _ = _climb(haiku, sonnet, budget=budget)
    assert outcome.carried and outcome.stood.status == "over_budget"
    assert sonnet.prompts == [], "no stronger model is asked once the day is spent"
    assert all(a.status in ("valid", "over_budget") for a in outcome.attempts)


def test_nothing_reached_the_question_leaves_nothing_standing():
    dossier, people = W.world()
    gate = G.RSiteGate(org_id=ORG, engine=None, client=_haiku(FAITHFUL), activated=frozenset(),
                       budget=B.NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG))
    outcome = L.run_ladder(org_id=ORG, dossier=dossier, fingerprint="ffp-1", people=people,
                           rungs=[L.Rung("T1", gate)], check=R.check)
    assert outcome.attempts == () and outcome.stood is None


def test_a_ladder_has_a_rung():
    dossier, people = W.world()
    with pytest.raises(ValueError, match="at least one rung"):
        L.run_ladder(org_id=ORG, dossier=dossier, fingerprint="f", people=people, rungs=[], check=R.check)


# ── what each consult keeps ────────────────────────────────────────────────────────────────────

def test_every_consult_has_a_key_of_its_own_and_a_refusal_keeps_its_check_and_its_reason():
    outcome, _ = _climb(_haiku(NOTHING, NOTHING), _sonnet(FAITHFUL))
    assert len({a.receipt.cache_key for a in outcome.attempts}) == len(outcome.attempts) == 3
    refused = outcome.attempts[0]
    assert refused.review is None and refused.checked.fate == C.REFUSED
    assert refused.reason.startswith("nothing_stands: fact:1 uncited")
    assert outcome.stood.review is not None and outcome.stood.reason is None


def test_a_review_misshapen_after_its_repair_is_a_failed_consult_not_a_refusal_on_substance():
    outcome, _ = _climb(_haiku({}, {}, {}, {}), _sonnet(FAITHFUL))
    assert [(a.status, a.fate) for a in outcome.attempts[:2]] == [("failed", None), ("failed", None)]
    assert outcome.attempts[0].reason.startswith("malformed")


def test_a_structure_the_contract_refuses_is_refused_whole_and_is_a_misshapen_answer_to_the_ladder():
    no_move = W.answer(move=False)
    outcome, _ = _climb(_haiku(no_move, no_move), _sonnet(FAITHFUL))
    first = outcome.attempts[0]
    assert first.status == "refused" and first.reason.startswith("no_next_move") and first.review is None
    assert outcome.attempts[1].climbed_because == "malformed"


def test_a_rung_that_cannot_be_asked_leaves_the_best_answer_so_far_standing():
    dossier, people = W.world()
    rungs, budget = _rungs(_haiku(HELD, HELD))
    off = G.RSiteGate(org_id=ORG, engine=None, client=_sonnet(FAITHFUL), activated=frozenset(), budget=budget)
    outcome = L.run_ladder(org_id=ORG, dossier=dossier, fingerprint="ffp-1", people=people,
                           rungs=[*rungs, L.Rung("T2", off)], check=R.check)
    assert len(outcome.attempts) == 2 and outcome.stood.fate == C.HELD and outcome.stood.consult == "repair"
    assert not outcome.carried

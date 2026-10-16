"""STEP-13b · a file's review climbs the ladder, and what stands is kept with every consult that led to it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_the_pass_climbs_and_counts.py

Tree `yc2_w27_s13b` M38.C2.L-integration.V11.U03 (`reason/expert/review.review_file`) and V12.U05 (`reason/expert/sweep`).
The row is the consult that STANDS — its model, its `rung`, the review and its check — and carries the cost and tokens of
every consult together; each consult is a row of `expert_review_attempts` (0250): rung, model, first or repair, status, the
check's fate and the closed reason it climbed. A lone gate is asked once, as before the ladder. The pass counts the
attempts, the climbs by reason, the cost by tier and which rung answered.
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.expert import ladder as L
from genios_engine.reason.expert import review as RV
from genios_engine.reason.expert import store as R
from tests.reason.expert import test_one_review as O
from tests.reason.expert.test_the_expert_pass import ORG as POOL_ORG, _files_of, _pass, world  # noqa: F401

pytestmark = pytest.mark.pg


class Tiered:
    """A model that answers in the mode its script says — `good` cites what the dossier prints, `bad` an id it never did."""

    def __init__(self, model, *modes):
        self.model, self.modes, self.prompts = model, list(modes), []

    def call(self, prompt, *, max_tokens=400, **_kw):
        self.prompts.append(prompt)
        mode = self.modes.pop(0) if self.modes else "good"
        evidence = re.search(r"\[(evt_[^\]\s]+)\]", prompt).group(1) if mode == "good" else "evt_never_printed"
        return LLMResult(parsed={
            "facts": [{"claim": "they wrote to us", "evidence": [evidence]}],
            "frames": {"primary": "a fund getting to know us", "rivals": ["a cold intro"]},
            "expected_vs_actual": {"stage": None, "expected": "a reply", "actual": "a reply came"},
            "scenarios": {"do_nothing": "it cools", "act": "it moves", "best": "a meeting", "worst": "silence",
                          "signals_to_watch": ["a reply"]},
            "appraisal": {"stakes": "medium", "urgency": "low", "reversibility": "reversible", "reasons": ["early"]},
            "mode": "wait", "wait_or_stop": "wait for their reply", "done_when": "they reply"},
            raw="{}", ok=True, model=self.model, input_tokens=9000, output_tokens=900)


def _attempts(store):
    with store.engine.connect() as c:
        return c.execute(text("select file_id, attempt_no, rung, model, consult, status, fate, climbed_because, "
                              "cost_micro_usd from expert_review_attempts where org_id = :o "
                              "order by file_id, attempt_no"), {"o": POOL_ORG}).fetchall()


def _rows(store):
    with store.engine.connect() as c:
        return c.execute(text("select file_id, status, model, rung, cost_micro_usd, input_tokens, output_tokens, "
                              "checked from expert_reviews where org_id = :o order by file_id"),
                         {"o": POOL_ORG}).fetchall()


def test_a_file_the_cheapest_model_answers_costs_one_consult_on_rung_one(world):
    store, now = world
    haiku, sonnet = Tiered("claude-haiku-4-5", "good", "good"), Tiered("claude-sonnet-5")
    receipt, _ = _pass(store, now, llm={"T1": haiku, "T2": sonnet})
    assert receipt["reviewed"] == {"valid": 2} and sonnet.prompts == []
    assert [(a.rung, a.model, a.consult, a.status, a.fate) for a in _attempts(store)] == [
        (1, "claude-haiku-4-5", "first", "valid", "shown")] * 2
    assert {(r.model, r.rung) for r in _rows(store)} == {("claude-haiku-4-5", 1)}
    assert receipt["attempts"] == {"T1:first": 2} and receipt["climbs"] == {} and receipt["stood"] == {"T1": 2}
    assert set(receipt["cost_by_tier"]) == {"T1"} and receipt["cost_micro_usd"] == receipt["cost_by_tier"]["T1"]


def test_a_failed_answer_is_repaired_once_on_its_rung_then_the_stronger_model_answers(world):
    store, now = world
    haiku, sonnet = Tiered("claude-haiku-4-5", *["bad"] * 4), Tiered("claude-sonnet-5", "good", "good")
    receipt, _ = _pass(store, now, llm={"T1": haiku, "T2": sonnet})
    assert receipt["reviewed"] == {"valid": 2} and len(haiku.prompts) == 4 and len(sonnet.prompts) == 2
    one = [a for a in _attempts(store) if a.file_id == _files_of(store)["evt_k_in"]]
    assert [(a.attempt_no, a.rung, a.consult, a.status, a.fate, a.climbed_because) for a in one] == [
        (1, 1, "first", "refused", "refused", None), (2, 1, "repair", "refused", "refused", "nothing_stands"),
        (3, 2, "first", "valid", "shown", None)]
    assert "unknown_evidence" in haiku.prompts[1] or "evt_never_printed" in haiku.prompts[1]
    rows = _rows(store)
    assert {(r.model, r.rung, r.status) for r in rows} == {("claude-sonnet-5", 2, "valid")}
    assert all(r.checked["fate"] == "shown" for r in rows)
    # the row carries the cost of every consult that led to it
    per_file = {}
    for a in _attempts(store):
        per_file[a.file_id] = per_file.get(a.file_id, 0) + a.cost_micro_usd
    assert {r.file_id: r.cost_micro_usd for r in rows} == per_file
    assert all(r.input_tokens == 27_000 and r.output_tokens == 2_700 for r in rows)
    assert receipt["climbs"] == {"nothing_stands": 2} and receipt["stood"] == {"T2": 2}
    assert receipt["attempts"] == {"T1:first": 2, "T1:repair": 2, "T2:first": 2}
    assert receipt["cost_micro_usd"] == sum(per_file.values())
    assert receipt["cost_by_tier"]["T1"] > 0 and receipt["cost_by_tier"]["T2"] > 0


def test_when_every_rung_failed_the_row_is_the_best_answer_and_says_why(world):
    store, now = world
    receipt, _ = _pass(store, now, llm={"T1": Tiered("claude-haiku-4-5", *["bad"] * 8),
                                        "T2": Tiered("claude-sonnet-5", *["bad"] * 8)})
    assert receipt["reviewed"] == {"refused": 2} and receipt["covered"] == {}
    rows = _rows(store)
    assert {r.status for r in rows} == {"refused"} and {r.rung for r in rows} == {2}, "a tie: the higher rung"
    assert len(_attempts(store)) == 8


def test_a_day_spent_mid_climb_carries_the_file_and_keeps_what_was_asked(world):
    store, now = world
    budget = B.NarrativeBudget(org_id=POOL_ORG, site=S.SITE_EXPERT, daily_cap_micro_usd=60_000,
                               per_call_cap_micro_usd=100_000)
    sonnet = Tiered("claude-sonnet-5")
    receipt, _ = _pass(store, now, budget=budget, llm={"T1": Tiered("claude-haiku-4-5", *["bad"] * 8), "T2": sonnet})
    assert receipt["reviewed"] == {"over_budget": 1} and sonnet.prompts == [] and receipt["carried"] == 1
    assert {a.status for a in _attempts(store)} <= {"refused", "over_budget"}
    assert [r.status for r in _rows(store)] == ["over_budget"]


def test_a_lone_client_is_asked_once_as_before_the_ladder(world):
    store, now = world
    lone = Tiered("claude-sonnet-5", "bad", "bad")
    receipt, _ = _pass(store, now, llm=lone)
    assert receipt["reviewed"] == {"refused": 2} and len(lone.prompts) == 2
    assert [(a.rung, a.consult) for a in _attempts(store)] == [(1, "first"), (1, "first")]


def test_the_opus_rung_is_off_until_the_tenant_allows_it(world):
    store, now = world
    with pytest.raises(ValueError, match="Opus rung is off"):
        _pass(store, now, llm={"T1": Tiered("a"), "T3": Tiered("b")})
    opus = Tiered("claude-opus-5-5")
    receipt, _ = _pass(store, now, llm={"T1": Tiered("a", *["bad"] * 8), "T3": opus}, allow_opus=True)
    # s13b-F20: the Opus rung's $0.20 per-call ceiling is unattainable at Opus 5.5's own output ceiling, so the budget
    # refuses its consult and the file is carried — the rung is built and stays OFF (s13b-D1) until that is decided.
    assert receipt["reviewed"] == {"over_budget": 1} and opus.prompts == [] and receipt["carried"] == 1
    assert {a.rung for a in _attempts(store)} == {1, 2}, "the rungs are the ones named: Haiku-class, then Opus-class"


def test_no_client_for_a_rung_is_no_model_configured(world, monkeypatch):
    store, now = world
    monkeypatch.setattr("genios_engine.reason.llm_sites.make_site_client", lambda tier: None)
    receipt = __import__("genios_engine.reason.expert.sweep", fromlist=["x"]).expert_pass(store=store, org_id=POOL_ORG, now=now)
    assert receipt == {"skipped": "no_model_configured"}

"""C5 · the LLM Decision Policy — the gate every R-site passes through, and the budget behind it.

    pytest tests/reason/test_llm_policy.py -q

`reason/` contained NO model call site before this wave. That is stricter than the doctrine asks
for and it is the direct cause of "mute", so this wave opens the first door in the layer — and this
file is the argument that opening it is safe. Seven steps, in order, every outcome on the record
including the ones where nothing ran, one retry and then a deterministic template, and a switch
that refuses every site at once so a replay can prove the decisions do not move.

The Postgres half needs GENIOS_TEST_DATABASE_URL, like every real-DB file here. The step-order half
does not, and it is the half that would have caught a gate that skipped a step.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from sqlalchemy import text

from genios_engine.platform.l4_activation import (
    FEATURE_BUNDLE,
    FEATURE_RANKING_V2,
)
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.bundle.gate import MAX_ATTEMPTS, RSiteGate, force_failed
from genios_engine.reason.bundle.store import BundleStore

ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK


# ── the fakes. A "model" that answers exactly what a case is about, and counts its calls. ─────

@dataclass
class FakeResult:
    parsed: dict
    raw: str = ""
    input_tokens: int = 900
    output_tokens: int = 300
    model: str = "claude-test-20260101"
    ok: bool = True
    error: str | None = None


class FakeLLM:
    model = "claude-test-20260101"

    def __init__(self, *answers, raises: bool = False) -> None:
        self.answers = list(answers)
        self.calls: list[str] = []
        self.raises = raises

    def call(self, prompt: str, *, max_tokens: int = 1000) -> FakeResult:
        self.calls.append(prompt)
        if self.raises:
            raise RuntimeError("the network is not a feature")
        if not self.answers:
            return FakeResult(parsed={}, ok=False, error="unparseable JSON")
        return self.answers.pop(0)


def _accept(parsed):
    return (parsed.get("value"), (), {"seen": True})


def _refuse(parsed):
    return (None, ("validator_said_no",), {"feedback": "- fix the thing"})


def _gate(**kwargs) -> RSiteGate:
    kwargs.setdefault("activated", frozenset({FEATURE_BUNDLE}))
    kwargs.setdefault("budget", B.NarrativeBudget(org_id=ORG))
    return RSiteGate(org_id=ORG, **kwargs)


def _consult(gate: RSiteGate, **kwargs):
    kwargs.setdefault("site", S.SITE_NARRATE)
    kwargs.setdefault("cache_key", "dec_abc")
    kwargs.setdefault("build_prompt", lambda feedback: "PROMPT" + (feedback or ""))
    kwargs.setdefault("validate", _accept)
    return gate.consult(**kwargs)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE SEVEN STEPS, IN ORDER
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_step_1_a_tenant_not_on_the_pilot_never_reaches_a_model():
    llm = FakeLLM(FakeResult(parsed={"value": "narrated"}))
    result = _consult(_gate(client=llm, activated=frozenset({FEATURE_RANKING_V2})))
    assert result.outcome == S.OUTCOME_NOT_ACTIVATED
    assert result.value is None and llm.calls == []
    assert result.cost_micro_usd == 0


def test_step_2_a_site_with_no_precondition_is_refused_and_says_which():
    """Doc 11 guard 7: an R-site fires on its own precondition, never 'just in case'."""
    llm = FakeLLM(FakeResult(parsed={"value": "narrated"}))
    result = _consult(_gate(client=llm), precondition=False,
                      precondition_reason="no_unresolved_ambiguity")
    assert result.outcome == S.OUTCOME_NO_PRECONDITION
    assert result.reason_codes == ("no_unresolved_ambiguity",)
    assert llm.calls == []


def test_step_3_the_cache_is_read_before_the_budget_and_before_any_prompt_is_built():
    """A hit costs nothing, so refusing one for want of budget would make a tenant's card go plain
    on a day that had already been paid for."""
    llm = FakeLLM(FakeResult(parsed={"value": "fresh"}))
    spent = B.NarrativeBudget(org_id=ORG, daily_cap_micro_usd=1)
    built: list[str] = []

    def _prompt(feedback):
        built.append("built")
        return "PROMPT"

    result = _consult(_gate(client=llm, budget=spent), build_prompt=_prompt,
                      cached=lambda: "already narrated")
    assert result.outcome == S.OUTCOME_CACHED
    assert result.value == "already narrated"
    assert llm.calls == [] and built == [], "a cache hit built a prompt it did not need"


def test_step_4_no_model_configured_is_its_own_outcome():
    """Distinct from a budget skip: one is a deployment fact and the other is a spend fact, and the
    fix for each lives somewhere different."""
    result = _consult(_gate(client=None))
    assert result.outcome == S.OUTCOME_NO_CLIENT
    assert result.value is None


def test_step_5_the_budget_is_checked_against_the_actual_prompt():
    llm = FakeLLM(FakeResult(parsed={"value": "narrated"}))
    tiny = B.NarrativeBudget(org_id=ORG, daily_cap_micro_usd=10)
    result = _consult(_gate(client=llm, budget=tiny))
    assert result.outcome == S.OUTCOME_NO_BUDGET
    assert result.reason_codes == (B.REASON_DAILY_EXHAUSTED,)
    assert llm.calls == [], "the budget was checked after the money was spent"


def test_step_6_a_rejected_generation_is_regenerated_exactly_once_then_falls_back():
    """Doc 05 §4 and doc 11 guard 4: one retry, never a storm."""
    llm = FakeLLM(FakeResult(parsed={"value": "bad"}), FakeResult(parsed={"value": "also bad"}),
                  FakeResult(parsed={"value": "would have been good"}))
    result = _consult(_gate(client=llm), validate=_refuse)
    assert len(llm.calls) == MAX_ATTEMPTS == 2
    assert result.outcome == S.OUTCOME_FAILED_VALIDATION
    assert result.value is None
    assert result.reason_codes == ("validator_said_no",)


def test_the_one_retry_carries_the_specific_complaint():
    """The single regeneration is the only chance to turn a near miss into a narrative, so it is
    told what to fix rather than that it was invalid."""
    llm = FakeLLM(FakeResult(parsed={"value": "bad"}), FakeResult(parsed={"value": "bad"}))
    _consult(_gate(client=llm), validate=_refuse)
    assert "- fix the thing" in llm.calls[1]
    assert "- fix the thing" not in llm.calls[0]


def test_a_generation_accepted_on_the_retry_is_a_ran_outcome():
    seen: list[int] = []

    def _validate(parsed):
        seen.append(1)
        if len(seen) == 1:
            return (None, ("nope",), {"feedback": "- try again"})
        return (parsed.get("value"), (), {})

    llm = FakeLLM(FakeResult(parsed={"value": "first"}), FakeResult(parsed={"value": "second"}))
    result = _consult(_gate(client=llm), validate=_validate)
    assert result.outcome == S.OUTCOME_RAN and result.value == "second"
    assert result.attempts == 2


def test_a_client_that_raises_is_a_failed_generation_and_never_an_exception():
    result = _consult(_gate(client=FakeLLM(raises=True)))
    assert result.outcome == S.OUTCOME_FAILED_GENERATION
    assert result.reason_codes == ("model_call_raised",)


def test_a_validator_that_raises_is_a_refusal_and_never_an_exception():
    def _boom(parsed):
        raise ZeroDivisionError("someone divided by the confidence")
    result = _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "x"}),
                                           FakeResult(parsed={"value": "x"}))), validate=_boom)
    assert result.outcome == S.OUTCOME_FAILED_VALIDATION
    assert "ZeroDivisionError" in result.reason_codes


def test_a_prompt_that_cannot_be_built_is_a_skip_and_never_an_exception():
    def _boom(feedback):
        raise KeyError("catalogue")
    result = _consult(_gate(client=FakeLLM()), build_prompt=_boom)
    assert result.outcome == S.OUTCOME_FAILED_GENERATION
    assert "prompt_build_failed" in result.reason_codes


def test_unparseable_json_is_told_apart_from_a_refused_generation():
    result = _consult(_gate(client=FakeLLM()))       # FakeLLM with no answers returns ok=False
    assert result.outcome == S.OUTCOME_FAILED_GENERATION
    assert result.reason_codes == ("unparseable_generation",)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE DOCTRINE SWITCH
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_force_failing_every_r_site_refuses_before_anything_is_built_or_spent():
    llm = FakeLLM(FakeResult(parsed={"value": "narrated"}))
    with force_failed():
        result = _consult(_gate(client=llm))
    assert result.outcome == S.OUTCOME_FORCE_FAILED
    assert llm.calls == [] and result.cost_micro_usd == 0


def test_the_force_fail_switch_is_its_own_outcome_and_not_a_reused_skip():
    """A force-failed run appearing in the ledger as an ordinary budget skip would make the
    doctrine test invisible after the fact."""
    assert S.OUTCOME_FORCE_FAILED not in {S.OUTCOME_NO_BUDGET, S.OUTCOME_NOT_ACTIVATED}
    assert S.OUTCOME_FORCE_FAILED in S.FALLBACK_OUTCOMES


def test_the_switch_restores_the_environment_it_found():
    before = os.environ.get("GENIOS_L4_FORCE_FAIL_R_SITES")
    with force_failed():
        pass
    assert os.environ.get("GENIOS_L4_FORCE_FAIL_R_SITES") == before


# ═════════════════════════════════════════════════════════════════════════════════════════════
# TIER DISCIPLINE AND MONEY  (doc 11)
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_tiers_are_the_ones_doc_11_budgeted():
    assert S.tier_for(S.SITE_NARRATE) == S.TIER_T2
    assert S.tier_for(S.SITE_INTERPRET) == S.TIER_T2
    assert S.tier_for(S.SITE_CONSULT) == S.TIER_T2
    assert S.tier_for(S.SITE_ALTERNATIVES) == S.TIER_T1, (
        "narration of already-decided alternatives is T1 — doc 11 guard 8")
    assert S.tier_for(S.SITE_EFFECT) == S.TIER_T1
    with pytest.raises(ValueError):
        S.tier_for("R-6")


def test_cost_is_integer_micro_dollars_and_rounds_up():
    """A bundle costs about a cent, so cents cannot express one; a float re-rounds differently on
    every worker. Rounding up means an estimate never authorises more than a human approved."""
    assert B.cost_micro_usd(tier="T2", input_tokens=1800, output_tokens=450) == 8100
    assert B.cost_micro_usd(tier="T1", input_tokens=1, output_tokens=0) == 1
    assert isinstance(B.cost_micro_usd(tier="T2", input_tokens=7, output_tokens=3), int)
    assert B.usd_to_micro("2.00") == 2_000_000 and B.usd_to_micro(0.05) == 50_000
    # THE CEILING, where it is actually observable. Every tier price is a whole number of cents per
    # million tokens, so the price division never has a remainder — the rounding that decides money
    # is the CHARACTERS-to-tokens one inside the pre-flight estimate. Five characters is two tokens,
    # not one: an estimate that rounded down would authorise slightly more than the ceiling a human
    # approved, once per call, forever.
    assert B.estimate_micro_usd(site=S.SITE_NARRATE, prompt_chars=5, max_output_tokens=0) == \
        B.cost_micro_usd(tier="T2", input_tokens=2, output_tokens=0)
    assert B.estimate_micro_usd(site=S.SITE_NARRATE, prompt_chars=4, max_output_tokens=0) == \
        B.cost_micro_usd(tier="T2", input_tokens=1, output_tokens=0)


def test_a_published_decision_costs_about_a_cent_to_explain():
    """Doc 11 §5's acceptance row, as a test rather than a table: R-2 at its budgeted shape must
    land under the $0.02 per-published-decision ceiling."""
    cost = B.cost_micro_usd(tier=S.tier_for(S.SITE_NARRATE), input_tokens=1800, output_tokens=450)
    assert cost <= B.usd_to_micro("0.02")


def test_the_budget_advances_in_process_so_the_ceiling_binds_within_one_sweep():
    """A ceiling re-read from the ledger on every call binds only BETWEEN calls, because the row
    for the call in flight is not written yet."""
    budget = B.NarrativeBudget(org_id=ORG, daily_cap_micro_usd=10_000)
    assert budget.check(4_000).allowed
    budget.charge(9_000)
    verdict = budget.check(4_000)
    assert not verdict.allowed and verdict.reason == B.REASON_DAILY_EXHAUSTED
    assert verdict.remaining_micro_usd == 1_000


def test_the_per_decision_ceiling_refuses_one_expensive_consult_on_a_fresh_day():
    budget = B.NarrativeBudget(org_id=ORG, daily_cap_micro_usd=10_000_000,
                               per_call_cap_micro_usd=1_000)
    verdict = budget.check(5_000)
    assert not verdict.allowed and verdict.reason == B.REASON_PER_CALL


def test_an_unreadable_ledger_fails_CLOSED_here_and_not_open():
    """The opposite of `wiring._spent_today_minor`, deliberately: refusing extraction stops the
    graph being built, and refusing narration costs a plainer sentence."""
    class Broken:
        def connect(self):
            raise RuntimeError("no")
    budget = B.NarrativeBudget(org_id=ORG, engine=Broken())
    verdict = budget.check(1)
    assert not verdict.allowed and verdict.reason == B.REASON_LEDGER_UNREADABLE


def test_zero_means_no_ceiling_the_same_way_it_does_for_the_platform_cap():
    budget = B.NarrativeBudget(org_id=ORG, daily_cap_micro_usd=0, per_call_cap_micro_usd=0)
    assert budget.check(9_999_999_999).allowed


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE RECEIPTS — a skip is a row  (Postgres)
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the consult ledger is not exercised")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture
def engine():
    eng = _engine()
    with eng.begin() as c:
        c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l4_reasoning_bundles where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l4_reasoning_bundles where org_id = :o"), {"o": ORG})


def _outcomes(engine) -> list[str]:
    with engine.connect() as c:
        return [row[0] for row in c.execute(text(
            "select outcome from l4_r_site_calls where org_id = :o order by id"), {"o": ORG})]


def test_every_gate_outcome_lands_on_the_record_including_the_skips(engine):
    """Doc 01 C5 step 2. A rate computed over successful calls cannot tell 'the narrative was quiet
    yesterday' from 'the narrative was refused by the budget yesterday'."""
    store = BundleStore(engine)
    _consult(_gate(client=None, store=store))
    _consult(_gate(client=FakeLLM(), store=store, activated=frozenset()))
    _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store))
    _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store),
             precondition=False)
    assert _outcomes(engine) == [S.OUTCOME_NO_CLIENT, S.OUTCOME_NOT_ACTIVATED,
                                 S.OUTCOME_RAN, S.OUTCOME_NO_PRECONDITION]


def test_a_run_records_its_tokens_its_cost_and_its_model(engine):
    store = BundleStore(engine)
    _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store))
    with engine.connect() as c:
        row = c.execute(text(
            "select input_tokens, output_tokens, cost_micro_usd, model, tier, attempts "
            "from l4_r_site_calls where org_id = :o"), {"o": ORG}).first()
    assert (row.input_tokens, row.output_tokens) == (900, 300)
    assert row.cost_micro_usd == B.cost_micro_usd(tier="T2", input_tokens=900, output_tokens=300)
    assert row.model == "claude-test-20260101" and row.tier == "T2" and row.attempts == 1


def test_the_narrative_ledger_is_this_layers_own_and_not_llm_costs(engine):
    """`llm_costs` records no site and no tier, so a narrative budget summed from it would go quiet
    because the tenant paid for extraction that morning. Both are written; only this one is the
    ceiling."""
    store = BundleStore(engine)
    recorded: list[dict] = []
    gate = _gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store,
                 cost_recorder=lambda **kwargs: recorded.append(kwargs))
    _consult(gate)
    assert store.spent_today_micro_usd(org_id=ORG) > 0
    assert recorded and recorded[0]["purpose"].startswith("l4_")
    assert recorded[0]["input_tokens"] == 900


def test_the_budget_opens_from_the_ledger_it_wrote(engine):
    store = BundleStore(engine)
    _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store))
    spent = store.spent_today_micro_usd(org_id=ORG)
    reopened = B.NarrativeBudget(org_id=ORG, engine=engine)
    assert reopened.spent_micro_usd == spent > 0


def test_a_broken_ledger_write_never_fails_a_consult(engine):
    """A receipt that can abort the thing it is a receipt for turns an accounting failure into a
    product failure. Wrapped in the store AND at the gate, because the gate accepts any store."""
    store = BundleStore(engine)
    store.record_call = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("disk full"))
    result = _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store))
    assert result.outcome == S.OUTCOME_RAN and result.value == "ok"


def test_k4_rates_are_computed_from_rows_and_in_basis_points(engine):
    store = BundleStore(engine)
    for _ in range(3):
        _consult(_gate(client=FakeLLM(FakeResult(parsed={"value": "ok"})), store=store))
    _consult(_gate(client=FakeLLM(), store=store), cached=lambda: "hit")
    stats = store.stats(org_id=ORG)
    assert stats["consults"][S.OUTCOME_RAN] == 3
    assert stats["consults"][S.OUTCOME_CACHED] == 1
    assert stats["cache_hit_rate_bp"] == 2500
    assert isinstance(stats["fallback_rate_bp"], int)
